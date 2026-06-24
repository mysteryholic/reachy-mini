"""Bidirectional local audio stream with optional settings UI."""

import os
import sys
import time
import asyncio
import logging
from typing import List, Optional
from pathlib import Path

from fastrtc import AdditionalOutputs, audio_to_float32
from scipy.signal import resample

from reachy_mini import ReachyMini
from reachy_mini.media.media_manager import MediaBackend
from reachy_robotis.config import LOCKED_PROFILE, config, resolve_env_path
from reachy_robotis.secret_utils import mask_api_key
from reachy_robotis.openai_realtime import OpenaiRealtimeHandler
from reachy_robotis.headless_personality_ui import mount_personality_routes


try:
    from fastapi import FastAPI, Response
    from pydantic import BaseModel
    from fastapi.responses import FileResponse, JSONResponse
    from starlette.staticfiles import StaticFiles
except Exception:  # pragma: no cover - only loaded when settings_app is used
    FastAPI = object  # type: ignore
    FileResponse = object  # type: ignore
    JSONResponse = object  # type: ignore
    StaticFiles = object  # type: ignore
    BaseModel = object  # type: ignore


logger = logging.getLogger(__name__)


class LocalStream:
    """LocalStream using Reachy Mini's recorder/player."""

    def __init__(
        self,
        handler: OpenaiRealtimeHandler,
        robot: ReachyMini,
        *,
        settings_app: Optional[FastAPI] = None,
        instance_path: Optional[str] = None,
    ):
        """Initialize the stream with an OpenAI realtime handler and pipelines."""
        self.handler = handler
        self._robot = robot
        self._stop_event = asyncio.Event()
        self._tasks: List[asyncio.Task[None]] = []
        self.handler._clear_queue = self.clear_audio_queue
        self._settings_app: Optional[FastAPI] = settings_app
        self._instance_path: Optional[str] = instance_path
        self._settings_initialized = False
        self._asyncio_loop = None

    def _env_path(self) -> Path:
        """Canonical .env path for persistence (always project root)."""
        return resolve_env_path()

    def _read_env_lines(self, env_path: Path) -> list[str]:
        """Load env file contents or a template as a list of lines."""
        inst = env_path.parent
        try:
            if env_path.exists():
                try:
                    return env_path.read_text(encoding="utf-8").splitlines()
                except Exception:
                    return []
            template_text = None
            ex = inst / ".env.example"
            if ex.exists():
                try:
                    template_text = ex.read_text(encoding="utf-8")
                except Exception:
                    template_text = None
            if template_text is None:
                try:
                    cwd_example = Path.cwd() / ".env.example"
                    if cwd_example.exists():
                        template_text = cwd_example.read_text(encoding="utf-8")
                except Exception:
                    template_text = None
            if template_text is None:
                packaged = Path(__file__).parent / ".env.example"
                if packaged.exists():
                    try:
                        template_text = packaged.read_text(encoding="utf-8")
                    except Exception:
                        template_text = None
            return template_text.splitlines() if template_text else []
        except Exception:
            return []

    def _persist_api_key(self, key: str) -> None:
        """Persist API key to environment and instance ``.env`` if possible."""
        k = (key or "").strip()
        if not k:
            return
        try:
            os.environ["OPENAI_API_KEY"] = k
        except Exception:
            pass
        try:
            config.OPENAI_API_KEY = k
        except Exception:
            pass

        try:
            env_path = self._env_path()
            env_path.parent.mkdir(parents=True, exist_ok=True)
            lines = self._read_env_lines(env_path)
            replaced = False
            for i, ln in enumerate(lines):
                if ln.strip().startswith("OPENAI_API_KEY="):
                    lines[i] = f"OPENAI_API_KEY={k}"
                    replaced = True
                    break
            if not replaced:
                lines.append(f"OPENAI_API_KEY={k}")
            final_text = "\n".join(lines) + "\n"
            env_path.write_text(final_text, encoding="utf-8")
            logger.info("Persisted OPENAI_API_KEY (%s) to %s", mask_api_key(k), env_path)

            try:
                from dotenv import load_dotenv

                load_dotenv(dotenv_path=str(env_path), override=True)
            except Exception:
                pass
        except Exception as e:
            logger.warning("Failed to persist OPENAI_API_KEY: %s", e)

    def _persist_personality(self, profile: Optional[str]) -> None:
        """Persist the startup personality to the instance .env and config."""
        if LOCKED_PROFILE is not None:
            return
        selection = (profile or "").strip() or None
        try:
            from reachy_robotis.config import set_custom_profile

            set_custom_profile(selection)
        except Exception:
            pass

        try:
            env_path = self._env_path()
            env_path.parent.mkdir(parents=True, exist_ok=True)
            lines = self._read_env_lines(env_path)
            replaced = False
            for i, ln in enumerate(list(lines)):
                if ln.strip().startswith("REACHY_MINI_CUSTOM_PROFILE="):
                    if selection:
                        lines[i] = f"REACHY_MINI_CUSTOM_PROFILE={selection}"
                    else:
                        lines.pop(i)
                    replaced = True
                    break
            if selection and not replaced:
                lines.append(f"REACHY_MINI_CUSTOM_PROFILE={selection}")
            if selection is None and not env_path.exists():
                return
            final_text = "\n".join(lines) + "\n"
            env_path.write_text(final_text, encoding="utf-8")
            logger.info("Persisted startup personality to %s", env_path)
            try:
                from dotenv import load_dotenv

                load_dotenv(dotenv_path=str(env_path), override=True)
            except Exception:
                pass
        except Exception as e:
            logger.warning("Failed to persist REACHY_MINI_CUSTOM_PROFILE: %s", e)

    def _read_persisted_personality(self) -> Optional[str]:
        """Read persisted startup personality from the project root .env (if any)."""
        env_path = self._env_path()
        try:
            if env_path.exists():
                for ln in env_path.read_text(encoding="utf-8").splitlines():
                    if ln.strip().startswith("REACHY_MINI_CUSTOM_PROFILE="):
                        _, _, val = ln.partition("=")
                        v = val.strip()
                        return v or None
        except Exception:
            pass
        return None

    def _init_settings_ui_if_needed(self) -> None:
        """Attach minimal settings UI to the settings app."""
        if self._settings_initialized:
            return
        if self._settings_app is None:
            return

        static_dir = Path(__file__).parent / "static"
        index_file = static_dir / "index.html"

        if hasattr(self._settings_app, "mount"):
            try:
                self._settings_app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            except Exception:
                pass

        class ApiKeyPayload(BaseModel):
            openai_api_key: str

        @self._settings_app.get("/")
        def _root():  # type: ignore[no-untyped-def]
            from starlette.responses import RedirectResponse

            return RedirectResponse(url="/chat")

        @self._settings_app.get("/favicon.ico")
        def _favicon() -> Response:
            return Response(status_code=204)

        @self._settings_app.get("/status")
        def _status() -> JSONResponse:
            has_key = bool(config.OPENAI_API_KEY and str(config.OPENAI_API_KEY).strip())
            return JSONResponse({"has_key": has_key})

        @self._settings_app.get("/ready")
        def _ready() -> JSONResponse:
            try:
                mod = sys.modules.get("reachy_robotis.tools.core_tools")
                ready = bool(getattr(mod, "_TOOLS_INITIALIZED", False)) if mod else False
            except Exception:
                ready = False
            return JSONResponse({"ready": ready})

        @self._settings_app.post("/openai_api_key")
        def _set_key(payload: ApiKeyPayload) -> JSONResponse:
            key = (payload.openai_api_key or "").strip()
            if not key:
                return JSONResponse({"ok": False, "error": "empty_key"}, status_code=400)
            self._persist_api_key(key)
            return JSONResponse({"ok": True})

        @self._settings_app.post("/validate_api_key")
        async def _validate_key(payload: ApiKeyPayload) -> JSONResponse:
            key = (payload.openai_api_key or "").strip()
            if not key:
                return JSONResponse({"valid": False, "error": "empty_key"}, status_code=400)

            try:
                import httpx

                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get("https://api.openai.com/v1/models", headers=headers)
                    if response.status_code == 200:
                        return JSONResponse({"valid": True})
                    elif response.status_code == 401:
                        return JSONResponse({"valid": False, "error": "invalid_api_key"}, status_code=401)
                    else:
                        return JSONResponse(
                            {"valid": False, "error": "validation_failed"}, status_code=response.status_code
                        )
            except Exception as e:
                logger.warning(f"API key validation failed: {e}")
                return JSONResponse({"valid": False, "error": "validation_error"}, status_code=500)

        class ChatTextPayload(BaseModel):
            text: str

        class ChatModePayload(BaseModel):
            mode: str = "hybrid"

        @self._settings_app.post("/chat/send")
        def _chat_send(payload: ChatTextPayload) -> JSONResponse:
            text = (payload.text or "").strip()
            if not text:
                return JSONResponse({"ok": False, "error": "empty text"}, status_code=400)
            ok = OpenaiRealtimeHandler.schedule_text_message(text)
            return JSONResponse({"ok": bool(ok)})

        @self._settings_app.get("/chat")
        def _chat_page() -> FileResponse:
            return FileResponse(str(index_file))

        @self._settings_app.get("/chat/messages")
        def _chat_messages(since: int = 0) -> JSONResponse:
            return JSONResponse(OpenaiRealtimeHandler.active_messages(int(since)))

        @self._settings_app.post("/chat/input_mode")
        def _chat_input_mode(payload: ChatModePayload) -> JSONResponse:
            only_chatting = str(payload.mode).strip().lower() == "only_chatting"
            ok = OpenaiRealtimeHandler.schedule_chat_only_mode(only_chatting)
            return JSONResponse({"ok": bool(ok), "mode": "only_chatting" if only_chatting else "hybrid"})

        self._settings_initialized = True

    def launch(self) -> None:
        """Start the recorder/player and run the async processing loops."""
        self._stop_event.clear()

        try:
            from dotenv import load_dotenv

            from reachy_robotis.config import set_custom_profile

            env_path = self._env_path()
            if env_path.exists():
                load_dotenv(dotenv_path=str(env_path), override=True)
                new_key = os.getenv("OPENAI_API_KEY", "").strip()
                if new_key:
                    try:
                        config.OPENAI_API_KEY = new_key
                    except Exception:
                        pass
                if LOCKED_PROFILE is None:
                    new_profile = os.getenv("REACHY_MINI_CUSTOM_PROFILE")
                    if new_profile is not None:
                        try:
                            set_custom_profile(new_profile.strip() or None)
                        except Exception:
                            pass
        except Exception:
            pass

        if os.getenv("REACHY_ROBOTIS_ENABLE_HF_FALLBACK", "0").strip().lower() in ("1", "true", "yes", "on"):
            if not (config.OPENAI_API_KEY and str(config.OPENAI_API_KEY).strip()):
                logger.info("OPENAI_API_KEY not set, attempting to download from HuggingFace...")
                try:
                    from gradio_client import Client
                    client = Client("HuggingFaceM4/gradium_setup", verbose=False)
                    key, status = client.predict(api_name="/claim_b_key")
                    if key and key.strip():
                        logger.info("Successfully downloaded API key from HuggingFace")
                        self._persist_api_key(key)
                except Exception as e:
                    logger.warning(f"Failed to download API key from HuggingFace: {e}")

        self._init_settings_ui_if_needed()

        if not (config.OPENAI_API_KEY and str(config.OPENAI_API_KEY).strip()):
            logger.warning("OPENAI_API_KEY not found. Open the app settings page to enter it.")
            try:
                while not (config.OPENAI_API_KEY and str(config.OPENAI_API_KEY).strip()):
                    time.sleep(0.2)
            except KeyboardInterrupt:
                logger.info("Interrupted while waiting for API key.")
                return

        self._robot.media.start_recording()
        self._robot.media.start_playing()
        time.sleep(1)

        async def runner() -> None:
            loop = asyncio.get_running_loop()
            self._asyncio_loop = loop  # type: ignore[assignment]
            try:
                if self._settings_app is not None:
                    mount_personality_routes(
                        self._settings_app,
                        self.handler,
                        lambda: self._asyncio_loop,
                        persist_personality=self._persist_personality,
                        get_persisted_personality=self._read_persisted_personality,
                    )
            except Exception:
                pass
            async def safe_handler_startup():
                """Wrap handler startup to prevent invalid API key from blocking console."""
                try:
                    await self.handler.start_up()
                except Exception as e:
                    logger.error(f"OpenAI Realtime handler startup failed (conversation unavailable): {e}")
                    await self._stop_event.wait()

            self._tasks = [
                asyncio.create_task(safe_handler_startup(), name="openai-handler"),
                asyncio.create_task(self.record_loop(), name="stream-record-loop"),
                asyncio.create_task(self.play_loop(), name="stream-play-loop"),
            ]
            try:
                await asyncio.gather(*self._tasks)
            except asyncio.CancelledError:
                logger.info("Tasks cancelled during shutdown")
            finally:
                await self.handler.shutdown()

        asyncio.run(runner())

    def close(self) -> None:
        """Stop the stream and underlying media pipelines."""
        logger.info("Stopping LocalStream...")

        try:
            self._robot.media.stop_recording()
        except Exception as e:
            logger.debug(f"Error stopping recording (may already be stopped): {e}")

        try:
            self._robot.media.stop_playing()
        except Exception as e:
            logger.debug(f"Error stopping playback (may already be stopped): {e}")

        self._stop_event.set()

        for task in self._tasks:
            if not task.done():
                task.cancel()

    def clear_audio_queue(self) -> None:
        """Flush the player's appsrc to drop any queued audio immediately."""
        logger.info("User intervention: flushing player queue")
        if self._robot.media.backend == MediaBackend.GSTREAMER:
            self._robot.media.audio.clear_player()
        elif self._robot.media.backend == MediaBackend.DEFAULT or self._robot.media.backend == MediaBackend.DEFAULT_NO_VIDEO:
            self._robot.media.audio.clear_output_buffer()
        self.handler.output_queue = asyncio.Queue()

    async def record_loop(self) -> None:
        """Read mic frames from the recorder and forward them to the handler."""
        input_sample_rate = self._robot.media.get_input_audio_samplerate()
        logger.debug(f"Audio recording started at {input_sample_rate} Hz")

        while not self._stop_event.is_set():
            audio_frame = self._robot.media.get_audio_sample()
            if audio_frame is not None:
                await self.handler.receive((input_sample_rate, audio_frame))
            await asyncio.sleep(0)

    async def play_loop(self) -> None:
        """Fetch outputs from the handler: log text and play audio frames."""
        while not self._stop_event.is_set():
            handler_output = await self.handler.emit()

            if isinstance(handler_output, AdditionalOutputs):
                for msg in handler_output.args:
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        logger.info(
                            "role=%s content=%s",
                            msg.get("role"),
                            content if len(content) < 500 else content[:500] + "…",
                        )

            elif isinstance(handler_output, tuple):
                input_sample_rate, audio_data = handler_output
                output_sample_rate = self._robot.media.get_output_audio_samplerate()

                if audio_data.ndim == 2:
                    if audio_data.shape[1] > audio_data.shape[0]:
                        audio_data = audio_data.T
                    if audio_data.shape[1] > 1:
                        audio_data = audio_data[:, 0]

                audio_frame = audio_to_float32(audio_data)

                if input_sample_rate != output_sample_rate:
                    audio_frame = resample(
                        audio_frame,
                        int(len(audio_frame) * output_sample_rate / input_sample_rate),
                    )

                self._robot.media.push_audio_sample(audio_frame)

            else:
                logger.debug("Ignoring output type=%s", type(handler_output).__name__)

            await asyncio.sleep(0)
