import json
import uuid
import base64
import random
import asyncio
import logging
from typing import Any, Final, Tuple, Literal, Optional
from pathlib import Path
from datetime import datetime

import cv2
import httpx
import numpy as np
import gradio as gr
from openai import AsyncOpenAI
from fastrtc import AdditionalOutputs, AsyncStreamHandler, wait_for_item, audio_to_int16
from numpy.typing import NDArray
from scipy.signal import resample
from websockets.exceptions import ConnectionClosedError

from reachy_robotis.config import (
    HF_BACKEND,
    OPENAI_BACKEND,
    config,
    get_hf_token,
    parse_hf_realtime_url,
)
from reachy_robotis.prompts import get_session_voice, get_session_instructions
from reachy_robotis.tools.core_tools import (
    ToolDependencies,
    get_tool_specs,
)
from reachy_robotis.tools.background_tool_manager import (
    ToolCallRoutine,
    ToolNotification,
    BackgroundToolManager,
)


logger = logging.getLogger(__name__)

OPEN_AI_INPUT_SAMPLE_RATE: Final[int] = 24000
OPEN_AI_OUTPUT_SAMPLE_RATE: Final[int] = 24000
# The Hugging Face realtime backend uses native-rate 16 kHz PCM.
HF_SAMPLE_RATE: Final[int] = 16000

AUDIO_INPUT_COST_PER_1M = 32.0
AUDIO_OUTPUT_COST_PER_1M = 64.0
TEXT_INPUT_COST_PER_1M = 4.0
TEXT_OUTPUT_COST_PER_1M = 16.0
IMAGE_INPUT_COST_PER_1M = 5.0

_RESPONSE_DONE_TIMEOUT: Final[float] = 30.0


def _compute_response_cost(usage: Any) -> float:
    """Compute dollar cost from a response usage object."""
    inp = getattr(usage, "input_token_details", None)
    out = getattr(usage, "output_token_details", None)
    cost = 0.0
    if inp:
        cost += (getattr(inp, "audio_tokens", 0) or 0) * AUDIO_INPUT_COST_PER_1M / 1e6
        cost += (getattr(inp, "text_tokens", 0) or 0) * TEXT_INPUT_COST_PER_1M / 1e6
        cost += (getattr(inp, "image_tokens", 0) or 0) * IMAGE_INPUT_COST_PER_1M / 1e6
    if out:
        cost += (getattr(out, "audio_tokens", 0) or 0) * AUDIO_OUTPUT_COST_PER_1M / 1e6
        cost += (getattr(out, "text_tokens", 0) or 0) * TEXT_OUTPUT_COST_PER_1M / 1e6
    return cost


_ENGLISH_LOCK = (
    "\n\nABSOLUTE LANGUAGE LOCK (highest priority, applies to every turn): "
    "Respond ONLY in English (en-US), both spoken and written. Never reply in "
    "Korean, Portuguese, Spanish, French, or any other language, even if the user "
    "speaks that language. No exceptions."
)


class OpenaiRealtimeHandler(AsyncStreamHandler):
    """An OpenAI realtime handler for fastrtc Stream."""

    _active_instance: "OpenaiRealtimeHandler | None" = None
    _chat_only_default: bool = False

    def __init__(self, deps: ToolDependencies, gradio_mode: bool = False, instance_path: Optional[str] = None):
        """Initialize the handler."""
        # Sample rate depends on the realtime backend: 24 kHz for OpenAI, native
        # 16 kHz for the Hugging Face endpoint. The robot-side resample adapts the
        # device rate to whichever value we set here.
        sample_rate = HF_SAMPLE_RATE if config.BACKEND_PROVIDER == HF_BACKEND else OPEN_AI_OUTPUT_SAMPLE_RATE

        super().__init__(
            expected_layout="mono",
            output_sample_rate=sample_rate,
            input_sample_rate=sample_rate,
        )

        self.deps = deps

        self.output_sample_rate = sample_rate
        self.input_sample_rate = sample_rate

        # Extra query params required when connecting to an allocated HF realtime
        # session (empty for OpenAI).
        self._realtime_connect_query: dict[str, str] = {}

        self.connection: Any = None
        self.output_queue: "asyncio.Queue[Tuple[int, NDArray[np.int16]] | AdditionalOutputs]" = asyncio.Queue()

        self.last_activity_time = asyncio.get_event_loop().time()
        self.start_time = asyncio.get_event_loop().time()
        self.is_idle_tool_call = False
        self.gradio_mode = gradio_mode
        self.instance_path = instance_path
        self._key_source: Literal["env", "textbox"] = "env"
        self._provided_api_key: str | None = None

        self.partial_transcript_task: asyncio.Task[None] | None = None
        self.partial_transcript_sequence: int = 0
        self.partial_debounce_delay = 0.5

        self._shutdown_requested: bool = False
        self._connected_event: asyncio.Event = asyncio.Event()

        self.tool_manager = BackgroundToolManager()

        self.cumulative_cost: float = 0.0

        self._pending_responses: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._response_done_event: asyncio.Event = asyncio.Event()
        self._response_done_event.set()
        self._last_response_rejected: bool = False

        import threading as _threading
        from collections import deque as _deque

        self._loop: asyncio.AbstractEventLoop | None = None
        self._transcript: "deque[dict[str, Any]]" = _deque(maxlen=200)
        self._transcript_seq: int = 0
        self._transcript_lock = _threading.Lock()
        self._text_chat_active: bool = False
        self._text_chat_focus_active: bool = False
        self._chat_only_mode: bool = type(self)._chat_only_default
        self._audio_input_muted_until: float = 0.0

    def _record_message(self, role: str, content: str) -> None:
        """Append a user/assistant text turn to the readable transcript buffer."""
        if not isinstance(content, str) or not content.strip():
            return
        with self._transcript_lock:
            self._transcript_seq += 1
            self._transcript.append({"id": self._transcript_seq, "role": role, "content": content})

    def get_messages(self, since: int = 0) -> dict[str, Any]:
        """Return transcript entries newer than ``since`` (and the latest id)."""
        with self._transcript_lock:
            messages = [dict(m) for m in self._transcript if m["id"] > since]
            latest = self._transcript_seq
        return {"messages": messages, "latest": latest}

    @classmethod
    def active_messages(cls, since: int = 0) -> dict[str, Any]:
        """Transcript accessor for the active handler (settings page polling)."""
        handler = cls._active_instance
        if handler is None:
            mode = "only_chatting" if cls._chat_only_default else "hybrid"
            return {
                "messages": [],
                "latest": since,
                "connected": False,
                "audio_muted": cls._chat_only_default,
                "chat_only_mode": cls._chat_only_default,
                "input_mode": mode,
            }
        data = handler.get_messages(since)
        data["connected"] = handler.connection is not None
        data["audio_muted"] = handler._audio_input_muted()
        data["chat_only_mode"] = handler._chat_only_mode
        data["input_mode"] = "only_chatting" if handler._chat_only_mode else "hybrid"
        return data

    def _audio_input_muted(self) -> bool:
        import time as _time

        return (
            self._chat_only_mode
            or self._text_chat_active
            or self._text_chat_focus_active
            or _time.monotonic() < self._audio_input_muted_until
        )

    def _set_text_chat_audio_mute(self, active: bool, hold_s: float = 0.0) -> None:
        import time as _time

        self._text_chat_active = active
        until = _time.monotonic() + hold_s
        if active:
            self._audio_input_muted_until = max(self._audio_input_muted_until, until)
        else:
            self._audio_input_muted_until = until

    async def _clear_input_audio_buffer(self) -> None:
        """Clear the server-side input audio buffer (OpenAI backend only).

        The Hugging Face realtime endpoint does not implement the
        ``input_audio_buffer.clear`` event and rejects it with an
        "Unknown or invalid event" error. Muting still works regardless, because
        ``_audio_input_muted_until`` stops audio from being appended.
        """
        if config.BACKEND_PROVIDER == HF_BACKEND:
            return
        if not self.connection:
            return
        await self.connection.input_audio_buffer.clear()

    async def _start_text_chat_audio_mute(self) -> None:
        self._set_text_chat_audio_mute(True, hold_s=30.0)
        if not self.connection:
            return
        try:
            await self._clear_input_audio_buffer()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not clear input audio buffer for typed chat mute: %s", exc)

    async def set_text_chat_audio_mute(self, enabled: bool, hold_s: float = 0.0) -> bool:
        import time as _time

        if enabled:
            self._text_chat_focus_active = True
            self._audio_input_muted_until = max(self._audio_input_muted_until, _time.monotonic() + 30.0)
            if self.connection:
                try:
                    await self._clear_input_audio_buffer()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Could not clear input audio buffer for chat focus mute: %s", exc)
        else:
            self._text_chat_focus_active = False
            self._audio_input_muted_until = _time.monotonic() + hold_s
        return True

    async def set_chat_only_mode(self, enabled: bool) -> bool:
        self._chat_only_mode = bool(enabled)
        OpenaiRealtimeHandler._chat_only_default = self._chat_only_mode
        if self._chat_only_mode and self.connection:
            try:
                await self._clear_input_audio_buffer()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Could not clear input audio buffer for chat-only mode: %s", exc)
        return True

    async def send_text_message(self, text: str, image_b64: str | None = None) -> bool:
        """Inject a typed user message into the live realtime conversation."""
        text = (text or "").strip()
        if not text:
            return False
        if not self.connection:
            logger.warning("send_text_message: no active realtime connection")
            return False
        try:
            await self._start_text_chat_audio_mute()
            self._record_message("user", text)
            await self.output_queue.put(AdditionalOutputs({"role": "user", "content": text}))
            content: list[dict[str, Any]] = [{"type": "input_text", "text": text}]
            if image_b64:
                content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"})
            await self.connection.conversation.item.create(
                item={"type": "message", "role": "user", "content": content},
            )
            await self._safe_response_create()
            return True
        except Exception as e:  # noqa: BLE001 - never crash the caller
            logger.warning("send_text_message failed: %s", e)
            self._set_text_chat_audio_mute(False)
            return False

    @classmethod
    def schedule_text_message(cls, text: str, timeout: float = 10.0, image_b64: str | None = None) -> bool:
        """Thread-safe entry point for the settings chat route to send typed text."""
        handler = cls._active_instance
        loop = getattr(handler, "_loop", None) if handler is not None else None
        if handler is None or loop is None:
            logger.warning("schedule_text_message: no active realtime handler")
            return False
        try:
            fut = asyncio.run_coroutine_threadsafe(handler.send_text_message(text, image_b64=image_b64), loop)
            return bool(fut.result(timeout=timeout))
        except Exception as e:  # noqa: BLE001
            logger.warning("schedule_text_message failed: %s", e)
            return False

    @classmethod
    def schedule_chat_only_mode(cls, enabled: bool, timeout: float = 3.0) -> bool:
        cls._chat_only_default = bool(enabled)
        handler = cls._active_instance
        loop = getattr(handler, "_loop", None) if handler is not None else None
        if handler is None or loop is None:
            return True
        try:
            fut = asyncio.run_coroutine_threadsafe(handler.set_chat_only_mode(enabled), loop)
            return bool(fut.result(timeout=timeout))
        except Exception as e:  # noqa: BLE001
            logger.warning("schedule_chat_only_mode failed: %s", e)
            return False

    def copy(self) -> "OpenaiRealtimeHandler":
        """Create a copy of the handler."""
        return OpenaiRealtimeHandler(self.deps, self.gradio_mode, self.instance_path)

    async def apply_personality(self, profile: str | None) -> str:
        """Apply a new personality (profile) at runtime if possible."""
        try:
            from reachy_robotis.config import config as _config
            from reachy_robotis.config import set_custom_profile

            set_custom_profile(profile)
            logger.info(
                "Set custom profile to %r (config=%r)", profile, getattr(_config, "REACHY_MINI_CUSTOM_PROFILE", None)
            )

            try:
                instructions = get_session_instructions()
                voice = get_session_voice()
            except BaseException as e:
                logger.error("Failed to resolve personality content: %s", e)
                return f"Failed to apply personality: {e}"

            if self.connection is not None:
                try:
                    await self.connection.session.update(
                        session={
                            "type": "realtime",
                            "instructions": instructions,
                            "audio": {"output": {"voice": voice}},
                        },
                    )
                    logger.info("Applied personality via live update: %s", profile or "built-in default")
                except Exception as e:
                    logger.warning("Live update failed; will restart session: %s", e)

                try:
                    await self._restart_session()
                    return "Applied personality and restarted realtime session."
                except Exception as e:
                    logger.warning("Failed to restart session after apply: %s", e)
                    return "Applied personality. Will take effect on next connection."
            else:
                logger.info(
                    "Applied personality recorded: %s (no live connection; will apply on next session)",
                    profile or "built-in default",
                )
                return "Applied personality. Will take effect on next connection."
        except Exception as e:
            logger.error("Error applying personality '%s': %s", profile, e)
            return f"Failed to apply personality: {e}"

    async def _emit_debounced_partial(self, transcript: str, sequence: int) -> None:
        """Emit partial transcript after debounce delay."""
        try:
            await asyncio.sleep(self.partial_debounce_delay)
            if self.partial_transcript_sequence == sequence:
                await self.output_queue.put(AdditionalOutputs({"role": "user_partial", "content": transcript}))
                logger.debug(f"Debounced partial emitted: {transcript}")
        except asyncio.CancelledError:
            logger.debug("Debounced partial cancelled")
            raise

    def _is_invalid_api_key_error(self, error: BaseException) -> bool:
        """Return True when a realtime close/error clearly reports an invalid API key."""
        message = str(error).casefold()
        return "invalid_api_key" in message or "invalid api key" in message

    async def _emit_api_key_error(self) -> None:
        """Surface invalid-key startup failures in the chat instead of a traceback."""
        await self.output_queue.put(
            AdditionalOutputs(
                {
                    "role": "assistant",
                    "content": (
                        "[error] OpenAI API key is invalid. "
                        "Update OPENAI_API_KEY in your environment or use the web settings page to save a valid key."
                    ),
                }
            )
        )

    async def _build_openai_client(self) -> AsyncOpenAI:
        """Build the OpenAI realtime client, resolving the API key as before."""
        openai_api_key = config.OPENAI_API_KEY
        if self.gradio_mode and not openai_api_key:
            await self.wait_for_args()  # type: ignore[no-untyped-call]
            args = list(self.latest_args)
            textbox_api_key = args[3] if len(args[3]) > 0 else None
            if textbox_api_key is not None:
                openai_api_key = textbox_api_key
                self._key_source = "textbox"
                self._provided_api_key = textbox_api_key
            else:
                openai_api_key = config.OPENAI_API_KEY
        else:
            if not openai_api_key or not openai_api_key.strip():
                logger.warning("OPENAI_API_KEY missing. Proceeding with a placeholder (tests/offline).")
                openai_api_key = "DUMMY"

        self._realtime_connect_query = {}
        return AsyncOpenAI(api_key=openai_api_key)

    async def _build_hf_client(self) -> AsyncOpenAI:
        """Allocate a Hugging Face realtime session and build an OpenAI-compatible client.

        The Pollen-managed proxy authenticates with the user's HF token and
        returns a ``connect_url`` for an allocated realtime session.
        """
        bearer_token = get_hf_token() or ""
        session_url = config.HF_REALTIME_SESSION_URL
        if not session_url:
            raise RuntimeError("Built-in Hugging Face session proxy URL is unavailable")

        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else None
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            response = await http_client.post(session_url, headers=headers)
            response.raise_for_status()
            payload = response.json()

        connect_url = payload.get("connect_url")
        if not isinstance(connect_url, str) or not connect_url:
            raise RuntimeError(f"Session allocator response did not contain a valid connect_url: {payload!r}")

        parsed = parse_hf_realtime_url(connect_url)
        self._realtime_connect_query = parsed.connect_query
        logger.info("Allocated Hugging Face realtime session %s", payload.get("session_id") or "<unknown>")
        return AsyncOpenAI(
            api_key=bearer_token or "DUMMY",
            base_url=parsed.base_url,
            websocket_base_url=parsed.websocket_base_url,
        )

    async def _build_realtime_client(self) -> AsyncOpenAI:
        """Build the realtime client for the configured backend provider."""
        if config.BACKEND_PROVIDER == HF_BACKEND:
            return await self._build_hf_client()
        return await self._build_openai_client()

    async def start_up(self) -> None:
        """Start the handler with minimal retries on unexpected websocket closure."""
        self.client = await self._build_realtime_client()

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                await self._run_realtime_session()
                return
            except ConnectionClosedError as e:
                if self._is_invalid_api_key_error(e):
                    logger.error("Realtime connection rejected: invalid OpenAI API key. Update OPENAI_API_KEY.")
                    await self._emit_api_key_error()
                    return
                logger.warning("Realtime websocket closed unexpectedly (attempt %d/%d): %s", attempt, max_attempts, e)
                if attempt < max_attempts:
                    base_delay = 2 ** (attempt - 1)
                    jitter = random.uniform(0, 0.5)
                    delay = base_delay + jitter
                    logger.info("Retrying in %.1f seconds...", delay)
                    await asyncio.sleep(delay)
                    # HF sessions are single-use/expiring, so re-allocate before retrying.
                    if config.BACKEND_PROVIDER == HF_BACKEND:
                        self.client = await self._build_realtime_client()
                    continue
                raise
            finally:
                self.connection = None
                try:
                    self._connected_event.clear()
                except Exception:
                    pass

    async def _restart_session(self) -> None:
        """Force-close the current session and start a fresh one in background."""
        try:
            if self.connection is not None:
                try:
                    await self.connection.close()
                except Exception:
                    pass
                finally:
                    self.connection = None

            if getattr(self, "client", None) is None:
                logger.warning("Cannot restart: realtime client not initialized yet.")
                return

            # HF sessions are single-use/expiring, so re-allocate a fresh one.
            if config.BACKEND_PROVIDER == HF_BACKEND:
                self.client = await self._build_realtime_client()

            try:
                self._connected_event.clear()
            except Exception:
                pass
            asyncio.create_task(self._run_realtime_session(), name="openai-realtime-restart")
            try:
                await asyncio.wait_for(self._connected_event.wait(), timeout=5.0)
                logger.info("Realtime session restarted and connected.")
            except asyncio.TimeoutError:
                logger.warning("Realtime session restart timed out; continuing in background.")
        except Exception as e:
            logger.warning("_restart_session failed: %s", e)

    async def _safe_response_create(self, **kwargs: Any) -> None:
        """Enqueue a response.create() kwargs for the sender worker _response_sender_loop()."""
        await self._pending_responses.put(kwargs)

    async def _response_sender_loop(self) -> None:
        """Dedicated worker that sends ``response.create()`` calls serially."""
        while self.connection:
            try:
                kwargs = await self._pending_responses.get()
            except asyncio.CancelledError:
                return

            sent = False
            max_retries = 5
            attempts = 0
            while not sent and self.connection and attempts < max_retries:
                try:
                    await asyncio.wait_for(self._response_done_event.wait(), timeout=_RESPONSE_DONE_TIMEOUT)
                except asyncio.TimeoutError:
                    logger.debug("Timed out waiting for previous response to finish; forcing ahead")
                    self._response_done_event.set()

                if not self.connection:
                    break

                self._last_response_rejected = False
                try:
                    await self.connection.response.create(**kwargs)
                except Exception as e:
                    logger.debug("_response_sender_loop: send failed: %s", e)
                    self._response_done_event.set()
                    break

                try:
                    await asyncio.wait_for(self._response_done_event.wait(), timeout=_RESPONSE_DONE_TIMEOUT)
                except asyncio.TimeoutError:
                    logger.debug("Timed out waiting for response.done; assuming response completed")
                    self._response_done_event.set()
                    break

                if self._last_response_rejected:
                    attempts += 1
                    if attempts >= max_retries:
                        logger.debug("response.create rejected %d times; giving up", attempts)
                        break
                    logger.debug("response.create was rejected; retrying (%d/%d)", attempts, max_retries)
                    continue

                sent = True

    async def _handle_tool_result(self, bg_tool: ToolNotification) -> None:
        """Process the result of a tool call."""
        if bg_tool.error is not None:
            logger.error("Tool '%s' (id=%s) failed with error: %s", bg_tool.tool_name, bg_tool.id, bg_tool.error)
            tool_result = {"error": bg_tool.error}
        elif bg_tool.result is not None:
            tool_result = bg_tool.result
            logger.info(
                "Tool '%s' (id=%s) executed successfully.",
                bg_tool.tool_name, bg_tool.id,
            )
            logger.debug("Tool '%s' full result: %s", bg_tool.tool_name, tool_result)
        else:
            logger.warning("Tool '%s' (id=%s) returned no result and no error", bg_tool.tool_name, bg_tool.id)
            tool_result = {"error": "No result returned from tool execution"}

        if not self.connection:
            logger.warning("Connection closed during tool '%s' (id=%s) execution; cannot send result back", bg_tool.tool_name, bg_tool.id)
            return

        try:
            if isinstance(bg_tool.id, str):
                await self.connection.conversation.item.create(
                    item={
                        "type": "function_call_output",
                        "call_id": bg_tool.id,
                        "output": json.dumps(tool_result),
                    },
                )

            await self.output_queue.put(
                AdditionalOutputs(
                    {
                        "role": "assistant",
                        "content": json.dumps(tool_result),
                        "metadata": {
                            "title": f"Used tool {bg_tool.tool_name}",
                            "status": "done",
                        },
                    },
                ),
            )

            if bg_tool.tool_name == "camera" and "b64_im" in tool_result:
                b64_im = tool_result["b64_im"]
                if not isinstance(b64_im, str):
                    logger.warning("Unexpected type for b64_im: %s", type(b64_im))
                    b64_im = str(b64_im)
                await self.connection.conversation.item.create(
                    item={
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_image",
                                "image_url": f"data:image/jpeg;base64,{b64_im}",
                            },
                        ],
                    },
                )
                logger.info("Added camera image to conversation")

                if self.deps.camera_worker is not None:
                    np_img = self.deps.camera_worker.get_latest_frame()
                    if np_img is not None:
                        rgb_frame = cv2.cvtColor(np_img, cv2.COLOR_BGR2RGB)
                    else:
                        rgb_frame = None
                    img = gr.Image(value=rgb_frame)

                    await self.output_queue.put(
                        AdditionalOutputs(
                            {
                                "role": "assistant",
                                "content": img,
                            },
                        ),
                    )

            if not bg_tool.is_idle_tool_call:
                await self._safe_response_create(
                    response={
                        "instructions": "Use the tool result just returned and answer concisely in speech.",
                    },
                )

            if self.deps.head_wobbler is not None:
                self.deps.head_wobbler.reset()

        except ConnectionClosedError:
            logger.warning("Connection closed while sending tool result")
            self.connection = None
            self._response_done_event.set()

    async def _run_realtime_session(self) -> None:
        """Establish and manage a single realtime session."""
        # The Hugging Face endpoint selects its own model (MODEL_NAME empty) and
        # requires the session's extra query params; OpenAI takes an explicit
        # model and no extra query. HF also uses native-rate PCM (rate=None).
        connect_kwargs: dict[str, Any] = {}
        if config.MODEL_NAME:
            connect_kwargs["model"] = config.MODEL_NAME
        if self._realtime_connect_query:
            connect_kwargs["extra_query"] = self._realtime_connect_query

        is_hf = config.BACKEND_PROVIDER == HF_BACKEND
        input_pcm_rate = None if is_hf else self.input_sample_rate
        output_pcm_rate = None if is_hf else self.output_sample_rate

        async with self.client.realtime.connect(**connect_kwargs) as conn:
            try:
                await conn.session.update(
                    session={
                        "type": "realtime",
                        "instructions": get_session_instructions() + _ENGLISH_LOCK,
                        "audio": {
                            "input": {
                                "format": {
                                    "type": "audio/pcm",
                                    "rate": input_pcm_rate,
                                },
                                "transcription": {"model": "gpt-4o-transcribe", "language": "en"},
                                "turn_detection": {
                                    "type": "server_vad",
                                    "interrupt_response": True,
                                },
                            },
                            "output": {
                                "format": {
                                    "type": "audio/pcm",
                                    "rate": output_pcm_rate,
                                },
                                "voice": get_session_voice(),
                            },
                        },
                        "tools": get_tool_specs(),  # type: ignore[typeddict-item]
                        "tool_choice": "auto",
                    },
                )
                logger.info(
                    "Realtime session initialized with profile=%r voice=%r",
                    getattr(config, "REACHY_MINI_CUSTOM_PROFILE", None),
                    get_session_voice(),
                )
                self._persist_api_key_if_needed()
            except ConnectionClosedError as e:
                if self._is_invalid_api_key_error(e):
                    logger.error("Realtime session.update rejected: invalid OpenAI API key. Update OPENAI_API_KEY.")
                    await self._emit_api_key_error()
                    return
                logger.warning("Realtime session.update failed because the websocket closed: %s", e)
                raise
            except Exception as e:
                if self._is_invalid_api_key_error(e):
                    logger.error("Realtime session.update rejected: invalid OpenAI API key. Update OPENAI_API_KEY.")
                    await self._emit_api_key_error()
                    return
                logger.exception("Realtime session.update failed; aborting startup")
                return

            logger.info("Realtime session updated successfully")

            self.connection = conn
            type(self)._active_instance = self
            self._loop = asyncio.get_event_loop()
            try:
                self._connected_event.set()
            except Exception:
                pass


            response_sender_task: asyncio.Task[None] | None = None
            try:
                self.tool_manager.start_up(tool_callbacks=[self._handle_tool_result])

                response_sender_task = asyncio.create_task(
                    self._response_sender_loop(), name="response-sender"
                )

                async for event in self.connection:
                    logger.debug(f"OpenAI event: {event.type}")
                    if event.type == "input_audio_buffer.speech_started":
                        if hasattr(self, "_clear_queue") and callable(self._clear_queue):
                            self._clear_queue()
                        if self.deps.head_wobbler is not None:
                            self.deps.head_wobbler.reset()
                        self.deps.movement_manager.set_listening(True)
                        logger.debug("User speech started")

                    if event.type == "input_audio_buffer.speech_stopped":
                        self.deps.movement_manager.set_listening(False)
                        logger.debug("User speech stopped - server will auto-commit with VAD")

                    if event.type in (
                        "response.audio.done",
                        "response.output_audio.done",
                        "response.audio.completed",
                        "response.completed",
                    ):
                        logger.debug("response completed")

                    if event.type == "response.created":
                        self._response_done_event.clear()
                        logger.debug("Response created (active)")

                    if event.type == "response.done":
                        self._response_done_event.set()
                        logger.debug("Response done")

                        response = getattr(event, "response", None)
                        usage = getattr(response, "usage", None) if response else None
                        if usage:
                            cost = _compute_response_cost(usage)
                            self.cumulative_cost += cost
                            logger.debug("Cost: $%.4f | Cumulative: $%.4f", cost, self.cumulative_cost)
                        else:
                            logger.warning("No usage data available for cost tracking")

                    if event.type == "conversation.item.input_audio_transcription.partial":
                        logger.debug(f"User partial transcript: {event.transcript}")

                        self.partial_transcript_sequence += 1
                        current_sequence = self.partial_transcript_sequence

                        if self.partial_transcript_task and not self.partial_transcript_task.done():
                            self.partial_transcript_task.cancel()
                            try:
                                await self.partial_transcript_task
                            except asyncio.CancelledError:
                                pass

                        self.partial_transcript_task = asyncio.create_task(
                            self._emit_debounced_partial(event.transcript, current_sequence)
                        )

                    if event.type == "conversation.item.input_audio_transcription.completed":
                        logger.debug(f"User transcript: {event.transcript}")

                        if self.partial_transcript_task and not self.partial_transcript_task.done():
                            self.partial_transcript_task.cancel()
                            try:
                                await self.partial_transcript_task
                            except asyncio.CancelledError:
                                pass

                        self._record_message("user", event.transcript)
                        await self.output_queue.put(AdditionalOutputs({"role": "user", "content": event.transcript}))

                    if event.type in ("response.audio_transcript.done", "response.output_audio_transcript.done"):
                        logger.debug(f"Assistant transcript: {event.transcript}")
                        self._record_message("assistant", event.transcript)
                        self._set_text_chat_audio_mute(False)
                        await self.output_queue.put(AdditionalOutputs({"role": "assistant", "content": event.transcript}))

                    if event.type in ("response.audio.delta", "response.output_audio.delta"):
                        if self.deps.head_wobbler is not None:
                            self.deps.head_wobbler.feed(event.delta)
                        self.last_activity_time = asyncio.get_event_loop().time()
                        logger.debug("last activity time updated to %s", self.last_activity_time)
                        await self.output_queue.put(
                            (
                                self.output_sample_rate,
                                np.frombuffer(base64.b64decode(event.delta), dtype=np.int16).reshape(1, -1),
                            ),
                        )

                    if event.type == "response.function_call_arguments.done":
                        tool_name = getattr(event, "name", None)
                        args_json_str = getattr(event, "arguments", None)
                        call_id: str = str(getattr(event, "call_id", uuid.uuid4()))

                        logger.info(
                            "Tool call received - tool_name=%r, call_id=%s, is_idle=%s, args=%s",
                            tool_name, call_id, self.is_idle_tool_call, args_json_str,
                        )

                        if not isinstance(tool_name, str) or not isinstance(args_json_str, str):
                            logger.error(
                                "Invalid tool call: tool_name=%s (type=%s), args=%s (type=%s), call_id=%s",
                                tool_name, type(tool_name).__name__,
                                args_json_str, type(args_json_str).__name__,
                                call_id,
                            )
                            continue

                        bg_tool = await self.tool_manager.start_tool(
                            call_id=call_id,
                            tool_call_routine=ToolCallRoutine(
                                tool_name=tool_name,
                                args_json_str=args_json_str,
                                deps=self.deps,
                            ),
                            is_idle_tool_call=self.is_idle_tool_call,
                        )

                        await self.output_queue.put(
                            AdditionalOutputs(
                                {
                                    "role": "assistant",
                                    "content": f"Used tool {tool_name} with args {args_json_str}. The tool is now running. Tool ID: {bg_tool.tool_id}",
                                },
                            ),
                        )

                        if self.is_idle_tool_call:
                            self.is_idle_tool_call = False

                        logger.info("Started background tool: %s (id=%s, call_id=%s)", tool_name, bg_tool.tool_id, call_id)

                    if event.type == "error":
                        err = getattr(event, "error", None)
                        msg = getattr(err, "message", str(err) if err else "unknown error")
                        code = getattr(err, "code", "")

                        if code == "conversation_already_has_active_response":
                            self._last_response_rejected = True
                            logger.debug("response.create rejected; worker will retry after active response finishes")
                        else:
                            logger.error("Realtime error [%s]: %s (raw=%s)", code, msg, err)

                        if code not in ("input_audio_buffer_commit_empty",):
                            await self.output_queue.put(
                                AdditionalOutputs({"role": "assistant", "content": f"[error] {msg}"})
                            )
            finally:
                if response_sender_task is not None:
                    response_sender_task.cancel()
                    try:
                        await response_sender_task
                    except asyncio.CancelledError:
                        pass

                await self.tool_manager.shutdown()

    async def receive(self, frame: Tuple[int, NDArray[np.int16]]) -> None:
        """Receive audio frame from the microphone and send it to the OpenAI server."""
        if not self.connection:
            return
        if self._audio_input_muted():
            return

        input_sample_rate, audio_frame = frame

        if audio_frame.ndim == 2:
            if audio_frame.shape[1] > audio_frame.shape[0]:
                audio_frame = audio_frame.T
            if audio_frame.shape[1] > 1:
                audio_frame = audio_frame[:, 0]

        if self.input_sample_rate != input_sample_rate:
            audio_frame = resample(audio_frame, int(len(audio_frame) * self.input_sample_rate / input_sample_rate))

        audio_frame = audio_to_int16(audio_frame)

        try:
            audio_message = base64.b64encode(audio_frame.tobytes()).decode("utf-8")
            await self.connection.input_audio_buffer.append(audio=audio_message)
        except Exception as e:
            logger.debug("Dropping audio frame: connection not ready (%s)", e)
            return

    async def emit(self) -> Tuple[int, NDArray[np.int16]] | AdditionalOutputs | None:
        """Emit audio frame to be played by the speaker."""

        idle_duration = asyncio.get_event_loop().time() - self.last_activity_time
        if idle_duration > 15.0 and self.deps.movement_manager.is_idle():
            try:
                await self.send_idle_signal(idle_duration)
            except Exception as e:
                logger.warning("Idle signal skipped (connection closed?): %s", e)
                return None

            self.last_activity_time = asyncio.get_event_loop().time()

        return await wait_for_item(self.output_queue)  # type: ignore[no-any-return]

    async def shutdown(self) -> None:
        """Shutdown the handler."""
        self._shutdown_requested = True

        self._response_done_event.set()

        await self.tool_manager.shutdown()

        if self.partial_transcript_task and not self.partial_transcript_task.done():
            self.partial_transcript_task.cancel()
            try:
                await self.partial_transcript_task
            except asyncio.CancelledError:
                pass

        if self.connection:
            try:
                await self.connection.close()
            except ConnectionClosedError as e:
                logger.debug(f"Connection already closed during shutdown: {e}")
            except Exception as e:
                logger.debug(f"connection.close() ignored: {e}")
            finally:
                self.connection = None

        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def format_timestamp(self) -> str:
        """Format current timestamp with date, time, and elapsed seconds."""
        loop_time = asyncio.get_event_loop().time()
        elapsed_seconds = loop_time - self.start_time
        dt = datetime.now()
        return f"[{dt.strftime('%Y-%m-%d %H:%M:%S')} | +{elapsed_seconds:.1f}s]"

    async def get_available_voices(self) -> list[str]:
        """Try to discover available voices for the configured realtime model."""
        fallback = [
            "cedar",
            "alloy",
            "aria",
            "ballad",
            "verse",
            "sage",
            "coral",
        ]
        try:
            model = await self.client.models.retrieve(config.MODEL_NAME)
            raw = None
            for attr in ("model_dump", "to_dict"):
                fn = getattr(model, attr, None)
                if callable(fn):
                    try:
                        raw = fn()
                        break
                    except Exception:
                        pass
            if raw is None:
                try:
                    raw = dict(model)
                except Exception:
                    raw = None
            candidates: set[str] = set()

            def _collect(obj: object) -> None:
                try:
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            kl = str(k).lower()
                            if "voice" in kl and isinstance(v, (list, tuple)):
                                for item in v:
                                    if isinstance(item, str):
                                        candidates.add(item)
                                    elif isinstance(item, dict) and "name" in item and isinstance(item["name"], str):
                                        candidates.add(item["name"])
                            else:
                                _collect(v)
                    elif isinstance(obj, (list, tuple)):
                        for it in obj:
                            _collect(it)
                except Exception:
                    pass

            if isinstance(raw, dict):
                _collect(raw)
            voices = sorted(candidates) if candidates else fallback
            if "cedar" not in voices:
                voices = ["cedar", *[v for v in voices if v != "cedar"]]
            return voices
        except Exception:
            return fallback

    async def send_idle_signal(self, idle_duration: float) -> None:
        """Send an idle signal to the openai server."""
        logger.debug("Sending idle signal")
        self.is_idle_tool_call = True
        timestamp_msg = f"[Idle time update: {self.format_timestamp()} - No activity for {idle_duration:.1f}s] You've been idle for a while. Feel free to get creative - dance, show an emotion, look around, do nothing, or just be yourself!"
        if not self.connection:
            logger.debug("No connection, cannot send idle signal")
            return
        await self.connection.conversation.item.create(
            item={
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": timestamp_msg}],
            },
        )
        await self._safe_response_create(
            response={
                "instructions": "You MUST respond with function calls only - no speech or text. Choose appropriate actions for idle behavior.",
                "tool_choice": "required",
            },
        )

    def _persist_api_key_if_needed(self) -> None:
        """Persist the API key into `.env` inside `instance_path/` when appropriate."""
        try:
            if not self.gradio_mode:
                logger.warning("Not in Gradio mode; skipping API key persistence.")
                return

            if self._key_source != "textbox":
                logger.info("API key not provided via textbox; skipping persistence.")
                return

            key = (self._provided_api_key or "").strip()
            if not key:
                logger.warning("No API key provided via textbox; skipping persistence.")
                return
            if self.instance_path is None:
                logger.warning("Instance path is None; cannot persist API key.")
                return

            try:
                import os

                os.environ["OPENAI_API_KEY"] = key
            except Exception:
                pass

            target_dir = Path(self.instance_path)
            env_path = target_dir / ".env"
            if env_path.exists():
                logger.info(".env already exists at %s; not overwriting.", env_path)
                return

            example_path = target_dir / ".env.example"
            content_lines: list[str] = []
            if example_path.exists():
                try:
                    content = example_path.read_text(encoding="utf-8")
                    content_lines = content.splitlines()
                except Exception as e:
                    logger.warning("Failed to read .env.example at %s: %s", example_path, e)

            replaced = False
            for i, line in enumerate(content_lines):
                if line.strip().startswith("OPENAI_API_KEY="):
                    content_lines[i] = f"OPENAI_API_KEY={key}"
                    replaced = True
                    break
            if not replaced:
                content_lines.append(f"OPENAI_API_KEY={key}")

            final_text = "\n".join(content_lines) + "\n"
            env_path.write_text(final_text, encoding="utf-8")
            logger.info("Created %s and stored OPENAI_API_KEY for future runs.", env_path)
        except Exception as e:
            logger.warning("Could not persist OPENAI_API_KEY to .env: %s", e)
