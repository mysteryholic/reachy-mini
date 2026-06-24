"""Entrypoint for the Reachy Mini conversation app."""

import os
import sys
import time
import asyncio
import argparse
import threading
from typing import Any, Dict, List, Optional


def parse_args():
    """Parse command line arguments (lazy import)."""
    from reachy_robotis.utils import parse_args as _parse_args
    return _parse_args()


def setup_logger(debug: bool):
    """Setup logger (lazy import)."""
    from reachy_robotis.utils import setup_logger as _setup_logger
    return _setup_logger(debug)


def handle_vision_stuff(args, robot):
    """Handle vision stuff (lazy import)."""
    from reachy_robotis.utils import handle_vision_stuff as _handle_vision_stuff
    return _handle_vision_stuff(args, robot)


def log_connection_troubleshooting(logger, robot_name):
    """Log connection troubleshooting (lazy import)."""
    from reachy_robotis.utils import log_connection_troubleshooting as _log_connection_troubleshooting
    return _log_connection_troubleshooting(logger, robot_name)


def update_chatbot(chatbot: List[Dict[str, Any]], response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Update the chatbot with AdditionalOutputs."""
    chatbot.append(response)
    return chatbot


def main() -> None:
    """Entrypoint for the Reachy Mini conversation app."""
    from reachy_robotis.cli import (
        list_tasks_command,
        describe_task_command,
        test_task_command,
        chat_mode_command,
        show_help,
    )

    # Check if a CLI command is being run
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "list-tasks":
            sys.exit(list_tasks_command())
        elif command == "describe-task":
            if len(sys.argv) < 3:
                print("Usage: reachy-robotis describe-task <task_name>")
                sys.exit(1)
            sys.exit(describe_task_command(sys.argv[2]))
        elif command == "test-task":
            if len(sys.argv) < 3:
                print("Usage: reachy-robotis test-task <task_name>")
                sys.exit(1)
            dry_run = "--dry-run" in sys.argv
            sys.exit(test_task_command(sys.argv[2], dry_run=dry_run))
        elif command == "chat":
            sys.exit(chat_mode_command())
        elif command in ("--help", "-h", "help"):
            sys.exit(show_help())

    args, _ = parse_args()
    run(args)


def run(
    args: argparse.Namespace,
    robot=None,
    app_stop_event: Optional[threading.Event] = None,
    settings_app=None,
    instance_path: Optional[str] = None,
) -> None:
    """Run the Reachy Mini conversation app."""
    # Lazy imports to avoid dependencies for CLI-only commands
    import gradio as gr
    from fastapi import FastAPI
    from fastapi.responses import RedirectResponse
    from fastrtc import Stream
    from gradio.utils import get_space
    from reachy_mini import ReachyMini, ReachyMiniApp

    # Putting these dependencies here makes the dashboard faster to load when the conversation app is installed
    from reachy_robotis.moves import MovementManager
    from reachy_robotis.console import LocalStream
    from reachy_robotis.openai_realtime import OpenaiRealtimeHandler
    from reachy_robotis.tools.core_tools import ToolDependencies
    from reachy_robotis.audio.head_wobbler import HeadWobbler
    from reachy_robotis.robotis_interface.web.routes import mount_robotis_routes

    logger = setup_logger(args.debug)
    logger.info("Starting Reachy Mini Conversation App")

    # HuggingFace API key fetch is opt-in only. Translate the explicit CLI flag
    # into the env switch that console.py honors; never fetch by default.
    if getattr(args, "allow_hf_key_fetch", False):
        os.environ["REACHY_ROBOTIS_ENABLE_HF_FALLBACK"] = "1"
        logger.warning("--allow-hf-key-fetch set: HuggingFace API key fetch is enabled for this run.")

    logger.warning(
        "SECURITY: if an OPENAI_API_KEY was ever printed to logs or committed, treat it as leaked. "
        "Revoke it at https://platform.openai.com/api-keys and issue a new key."
    )

    if args.no_camera and args.head_tracker is not None:
        logger.warning(
            "Head tracking disabled: --no-camera flag is set. "
            "Remove --no-camera to enable head tracking."
        )

    if robot is None:
        try:
            robot_kwargs = {}
            if args.robot_name is not None:
                robot_kwargs["robot_name"] = args.robot_name

            logger.info("Initializing ReachyMini (SDK will auto-detect appropriate backend)")
            robot = ReachyMini(**robot_kwargs)

        except TimeoutError as e:
            logger.error(
                "Connection timeout: Failed to connect to Reachy Mini daemon. "
                f"Details: {e}"
            )
            log_connection_troubleshooting(logger, args.robot_name)
            sys.exit(1)

        except ConnectionError as e:
            logger.error(
                "Connection failed: Unable to establish connection to Reachy Mini. "
                f"Details: {e}"
            )
            log_connection_troubleshooting(logger, args.robot_name)
            sys.exit(1)

        except Exception as e:
            logger.error(
                f"Unexpected error during robot initialization: {type(e).__name__}: {e}"
            )
            logger.error("Please check your configuration and try again.")
            sys.exit(1)

    # Auto-enable Gradio in simulation mode (both MuJoCo for daemon and mockup-sim for desktop app)
    status = robot.client.get_status()
    if isinstance(status, dict):
        simulation_enabled = status.get("simulation_enabled", False)
        mockup_sim_enabled = status.get("mockup_sim_enabled", False)
    else:
        simulation_enabled = getattr(status, "simulation_enabled", False)
        mockup_sim_enabled = getattr(status, "mockup_sim_enabled", False)

    is_simulation = simulation_enabled or mockup_sim_enabled

    if is_simulation and not args.gradio:
        logger.info("Simulation mode detected. Automatically enabling gradio flag.")
        args.gradio = True
    # A standalone run uses LocalStream (robot mic/speaker conversation) and
    # self-hosts the web UI — chat panel at "/", control panel at "/robotis" —
    # mirroring the reference app. Pass --gradio to use the browser /chat audio UI.

    camera_worker, _, vision_manager = handle_vision_stuff(args, robot)

    movement_manager = MovementManager(
        current_robot=robot,
        camera_worker=camera_worker,
    )

    head_wobbler = HeadWobbler(set_speech_offsets=movement_manager.set_speech_offsets)

    deps = ToolDependencies(
        reachy_mini=robot,
        movement_manager=movement_manager,
        camera_worker=camera_worker,
        vision_manager=vision_manager,
        head_wobbler=head_wobbler,
    )
    current_file_path = os.path.dirname(os.path.abspath(__file__))
    logger.debug(f"Current file absolute path: {current_file_path}")
    chatbot = gr.Chatbot(
        type="messages",
        resizable=True,
        avatar_images=(
            os.path.join(current_file_path, "images", "user_avatar.png"),
            os.path.join(current_file_path, "images", "reachymini_avatar.png"),
        ),
    )
    logger.debug(f"Chatbot avatar images: {chatbot.avatar_images}")

    handler = OpenaiRealtimeHandler(deps, gradio_mode=args.gradio, instance_path=instance_path)

    stream_manager: gr.Blocks | LocalStream | None = None
    # True when we self-host the LocalStream web UI for a standalone run.
    standalone_web = False

    if args.gradio:
        api_key_textbox = gr.Textbox(
            label="OPENAI API Key",
            type="password",
            value=os.getenv("OPENAI_API_KEY") if not get_space() else "",
        )

        from reachy_robotis.gradio_personality import PersonalityUI

        personality_ui = PersonalityUI()
        personality_ui.create_components()

        stream = Stream(
            handler=handler,
            mode="send-receive",
            modality="audio",
            additional_inputs=[
                chatbot,
                api_key_textbox,
                *personality_ui.additional_inputs_ordered(),
            ],
            additional_outputs=[chatbot],
            additional_outputs_handler=update_chatbot,
            ui_args={"title": "Talk with Reachy Mini"},
        )
        stream_manager = stream.ui
        if not settings_app:
            app = FastAPI()
        else:
            app = settings_app

        mount_robotis_routes(app, camera_worker=camera_worker)

        @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
        async def robot_action_interface_root() -> RedirectResponse:
            return RedirectResponse(url="/chat")

        personality_ui.wire_events(handler, stream_manager)

        # Register the fastrtc WebRTC signaling routes (/chat/webrtc/offer,
        # /chat/websocket/offer, telephone) BEFORE mounting the Gradio sub-app,
        # otherwise the /chat mount shadows them and the mic/buttons get a 404
        # on the WebRTC handshake (UI loads but nothing responds).
        stream.mount(app, path="/chat")

        app = gr.mount_gradio_app(app, stream.ui, path="/chat")
    else:
        # LocalStream conversation (robot mic/speaker). Serve the web UI on a
        # FastAPI app: chat page at "/", robot workflow panel at "/robotis". The Reachy
        # Mini daemon supplies that app; for a standalone run we host one ourselves.
        if settings_app is None:
            settings_app = FastAPI()
            standalone_web = True
        mount_robotis_routes(settings_app, camera_worker=camera_worker)
        stream_manager = LocalStream(
            handler,
            robot,
            settings_app=settings_app,
            instance_path=instance_path,
        )

    # Each async service → its own thread/loop
    movement_manager.start()
    head_wobbler.start()
    if camera_worker:
        camera_worker.start()
    if vision_manager:
        vision_manager.start()

    def poll_stop_event() -> None:
        """Poll the stop event to allow graceful shutdown."""
        if app_stop_event is not None:
            app_stop_event.wait()

        logger.info("App stop event detected, shutting down...")
        try:
            stream_manager.close()
        except Exception as e:
            logger.error(f"Error while closing stream manager: {e}")

    if app_stop_event:
        threading.Thread(target=poll_stop_event, daemon=True).start()

    try:
        if args.gradio and app_stop_event is None:
            # Standalone gradio run: serve the combined FastAPI app (Chat /
            # Voice at "/" and "/chat", Robot Launcher at "/robotis")
            # with uvicorn on all
            # interfaces, so the app is reachable at http://<robot-ip>:7860/ and
            # /robotis/* works on the same port. gr.Blocks.launch() would bind
            # 127.0.0.1 only and would not serve the /robotis routes.
            import uvicorn

            server_name = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
            server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
            logger.info(
                "Serving app on http://%s:%d (chat/voice at /, robot launcher at /robotis)",
                server_name,
                server_port,
            )
            uvicorn.run(app, host=server_name, port=server_port)
        else:
            # Standalone non-gradio: serve the self-hosted web UI (chat at "/",
            # robot action interface at "/robotis") in a background thread, then
            # run the conversation loops (blocking, robot mic/speaker).
            if standalone_web:
                import uvicorn

                server_name = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
                server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
                logger.info(
                    "Serving app on http://%s:%d (chat at /, robot action interface at /robotis)",
                    server_name,
                    server_port,
                )
                _web_server = uvicorn.Server(
                    uvicorn.Config(settings_app, host=server_name, port=server_port, log_level="info")
                )
                threading.Thread(target=_web_server.run, name="reachy-robotis-web", daemon=True).start()
            stream_manager.launch()
    except KeyboardInterrupt:
        logger.info("Keyboard interruption in main thread... closing server.")
    finally:
        movement_manager.stop()
        head_wobbler.stop()
        if camera_worker:
            camera_worker.stop()
        if vision_manager:
            vision_manager.stop()

        # Ensure media is explicitly closed before disconnecting
        try:
            robot.media.close()
        except Exception as e:
            logger.debug(f"Error closing media during shutdown: {e}")

        # prevent connection to keep alive some threads
        robot.client.disconnect()
        time.sleep(1)
        logger.info("Shutdown complete.")


# Lazy import for ReachyMiniApp (only needed when running as Reachy Mini app)
try:
    from reachy_mini import ReachyMiniApp
except ImportError:
    ReachyMiniApp = object  # Fallback for CLI-only environments


class ReachyRobotis(ReachyMiniApp):  # type: ignore[misc]
    """Reachy Mini Apps entry point for the conversation app."""

    custom_app_url = "http://0.0.0.0:7860/"
    dont_start_webserver = False

    def run(self, reachy_mini, stop_event: threading.Event) -> None:
        """Run the Reachy Mini conversation app."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        args, _ = parse_args()

        # is_wireless = reachy_mini.client.get_status()["wireless_version"]
        # args.head_tracker = None if is_wireless else "mediapipe"

        instance_path = self._get_instance_path().parent
        run(
            args,
            robot=reachy_mini,
            app_stop_event=stop_event,
            settings_app=self.settings_app,
            instance_path=instance_path,
        )


if __name__ == "__main__":
    main()
