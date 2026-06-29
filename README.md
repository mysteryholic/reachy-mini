---
title: Reachy Robotis
colorFrom: purple
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
tags:
  - reachy_mini
  - reachy_mini_python_app
---

# Reachy Robotis

Reachy Robotis extends the Reachy Mini conversation app with a ROBOTIS device execution interface. The current implementation is more than a demo chat app: it accepts voice, text, and web UI input, resolves that input into registered actions, and runs workflows or commands for OMX, OMY, AI Worker, HX5 Hand, and mock devices.

The main runtime flow is:

```text
User voice / text / web UI
  -> Reachy Mini conversation app
  -> OpenAI or Hugging Face realtime backend
  -> tool/function calling
  -> ROBOTIS intent resolver
  -> action / recipe / task / command catalog
  -> ActionExecutor
  -> device adapter
  -> SSH, Docker, ROS 2, HTTP bridge, or mock transport
```

> Security warning
>
> An earlier build stored `OPENAI_API_KEY` in `src/reachy_robotis/.env`, and the raw key may have appeared in logs or search results. Treat any exposed key as compromised, revoke it, and create a new key at https://platform.openai.com/api-keys.
>
> The current implementation prefers the project-root `.env`. If an older `src/reachy_robotis/.env` file is found, the app attempts to migrate it to the root `.env`. Keys are masked in logs, API responses, and UI output. Automatic OpenAI key retrieval from Hugging Face is disabled by default and is only enabled when `--allow-hf-key-fetch` is passed explicitly.

## Current Implementation

- The Python package is `reachy_robotis`, and the CLI entrypoint is `reachy-robotis`.
- The main app creates a Reachy Mini SDK `ReachyMini` object and wires together `MovementManager`, `HeadWobbler`, the camera worker, the vision manager, and the realtime handler.
- In Gradio/FastAPI web mode, `/chat` serves the conversation and voice UI, while `/robotis` serves the ROBOTIS product launcher and execution API.
- In headless mode, the app can still mount the `/robotis` API and panel on the FastAPI settings app while connecting the Reachy Mini microphone and speaker to the realtime backend through the local audio stream.
- The ROBOTIS execution layer is split into `TaskCatalog`, `CommandCatalog`, `ActionCatalog`, `RecipeCatalog`, `ConnectionRegistry`, `DeviceRegistry`, `TerminalSessionManager`, and `ActionExecutor`.
- Device adapters support `reachy`, `omx`, `omy`, `ai_worker`, and `mock`.
- Transports include local/mock execution, SSH, SSH+Docker, WebSocket, HTTP, and the OMX bridge.
- Configuration and workflows are defined in YAML files. The web UI can save or update selected connection settings and workflows.
- Tests cover the connection registry, external loading, OpenAI realtime handling, background tool management, audio head wobble behavior, and vision processors.

## Installation

This repository is designed to use `uv`.

```bash
uv sync
```

The commands below use `uv run ...`. If you already activated `.venv` directly, you can omit the `uv run` prefix.

Install development dependencies with:

```bash
uv sync --group dev
```

Install optional vision backends with the extras defined in `pyproject.toml`:

```bash
uv sync --extra local_vision
uv sync --extra yolo_vision
uv sync --extra mediapipe_vision
uv sync --extra all_vision
```

## Environment Variables

Configure the app through the project-root `.env` file or shell environment variables.

```bash
cp .env.example .env
```

Important values:

- `BACKEND_PROVIDER`: `huggingface` or `openai`. The default is `huggingface`.
- `OPENAI_API_KEY`: Required when `BACKEND_PROVIDER=openai`.
- `HF_TOKEN`: May be required for the Hugging Face realtime backend. You can also configure it with `hf auth login`.
- `MODEL_NAME`: Realtime model used by the OpenAI backend. The default is `gpt-realtime`.
- `LOCAL_VISION_MODEL`: Local vision model used with `--local-vision`. The default is `HuggingFaceTB/SmolVLM2-2.2B-Instruct`.
- `ROBOTIS_CLI_DRY_RUN`: Set to `1` to avoid real command execution, or `0` to allow live execution.
- `GRADIO_SERVER_NAME`, `GRADIO_SERVER_PORT`: Web server host and port. The default port is `7860`.
- `REACHY_MINI_SKIP_DOTENV`: Skip automatic `.env` loading.
- `REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY`, `REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY`, `AUTOLOAD_EXTERNAL_TOOLS`: Configure external personality and tool loading.

## Running

Start a simulator or a real Reachy Mini daemon first.

```bash
uv run reachy-mini-daemon --sim
```

Start the web UI:

```bash
uv run reachy-robotis --gradio
```

Open these URLs in a browser:

- `http://localhost:7860/chat`: Reachy Mini voice and chat interface
- `http://localhost:7860/robotis`: ROBOTIS product launcher
- `http://localhost:7860/robotis/health`: Health check API

Run in headless mode with:

```bash
uv run reachy-robotis
```

If simulation mode is detected and `--gradio` is not provided, the app automatically enables Gradio mode.

Common options:

```bash
uv run reachy-robotis --gradio --debug
uv run reachy-robotis --no-camera
uv run reachy-robotis --head-tracker yolo
uv run reachy-robotis --head-tracker mediapipe
uv run reachy-robotis --local-vision
uv run reachy-robotis --robot-name <same-name-as-the-daemon>
uv run reachy-robotis --allow-hf-key-fetch
```

Stop the app with `Ctrl+C`. During shutdown, the app stops the movement manager, head wobbler, camera worker, and vision manager, then closes the robot media/client connections.

## CLI

`src/reachy_robotis/main.py` handles a few subcommands before normal app startup.

```bash
uv run reachy-robotis list-tasks
uv run reachy-robotis describe-task <task_name>
uv run reachy-robotis test-task <task_name>
uv run reachy-robotis chat
uv run reachy-robotis --help
```

The `chat` mode is a text-only way to test registered task triggers or task names without voice.

```text
>> list
>> describe push_box_custom
>> push the box
>> push_box_custom
>> status
>> exit
```

Note: `test-task` is currently a preview helper rather than a live robot executor. If the task device is not `mock`, it warns that real motion may be possible.

## Web UI

### `/chat`

This is the realtime conversation UI. The current implementation uses FastRTC `Stream` and `OpenaiRealtimeHandler`.

- Voice input and output
- Text chat injection
- Conversation transcript storage
- Audio input mute while text chat is active
- 16 kHz PCM for the Hugging Face backend and 24 kHz PCM for the OpenAI backend
- Reachy Mini and ROBOTIS tool execution through tool/function calling
- Gradio personality UI integration

### `/robotis`

This is the ROBOTIS product and workflow launcher.

- Product launcher with a simplified product selector
- Connection setting save flow
- Connection test flow
- Workflow start/stop controls
- Last result view with stdout/stderr tails
- Global stop
- WebSocket status refresh every second
- Camera live stream and object detection API
- Task save/delete/export API
- Recipe save/delete/run/stop API
- Connection profile read/save/test API
- Device-specific allowlisted command execution API

Main API surface:

```text
GET    /robotis/health
GET    /robotis/status
GET    /robotis/ui/summary
GET    /robotis/actions
POST   /robotis/actions/run
POST   /robotis/intent/resolve
POST   /robotis/stop
POST   /robotis/actions/cancel
GET    /robotis/products
POST   /robotis/products/{product_id}/connection
POST   /robotis/products/{product_id}/test
PUT    /robotis/products/{product_id}/workflows/{workflow_id}
POST   /robotis/products/{product_id}/workflows/{workflow_id}
GET    /robotis/connections
POST   /robotis/connections/{connection_id}
POST   /robotis/connections/{connection_id}/test
GET    /robotis/recipes
POST   /robotis/recipes/{recipe_id}
POST   /robotis/recipes/{recipe_id}/run
POST   /robotis/recipes/{recipe_id}/stop
GET    /robotis/sessions
POST   /robotis/sessions/{session_id}/stop
GET    /robotis/camera/status
GET    /robotis/camera/snapshot
GET    /robotis/camera/detections
POST   /robotis/camera/detections/refresh
POST   /robotis/camera/detections/warmup
WS     /robotis/ws
WS     /robotis/omx/teleop
WS     /robotis/omx/task
```

## ROBOTIS Execution Architecture

ROBOTIS execution is handled by the process-wide executor assembled by `get_robotis_executor()`.

Core components:

- `DeviceRegistry`: Loads `config/robotis_devices.yaml` and manages each device mode, host, user, container, and allowlisted commands.
- `ConnectionRegistry`: Manages SSH/Docker connection profiles from `config/robotis_connections.yaml`. Secret values are never exposed in API responses.
- `TaskCatalog`: Loads manual tasks from `tasks/*.yaml`.
- `CommandCatalog`: Loads registered commands.
- `ActionCatalog`: Loads trigger-based actions from `config/robotis_actions.yaml`.
- `RecipeCatalog`: Loads multi-terminal workflows from `config/robotis_recipes.yaml`.
- `ProductPresetCatalog`: Installs product presets from `config/robotis_product_presets.yaml` and enriches actions, recipes, and connections.
- `TerminalSessionManager`: Starts recipe terminals in `start_order` order and stops them in reverse order.
- `IntentResolver`: Resolves user text into task, command, action, or recipe triggers.
- `ActionExecutor`: Dispatches resolved work to the actual adapter and transport.

Supported adapters:

- `ReachyAdapter`: Reachy Mini conversation app actions
- `OMXAdapter`: OMX tasks, bridge, teleoperation, and command execution
- `OMYAdapter`: OMY Raspberry Pi and ROS workflow execution
- `AIWorkerAdapter`: Jetson Orin AI Worker workflow execution
- `MockAdapter`: Test flow without real hardware

Supported transports:

- `MockTransport`
- `CLITransport`
- `ConnectionTransport`
- `SSHDockerTransport`
- `SSHLocalTransport`
- `HTTPTransport`
- `WebSocketTransport`
- `OMXBridgeTransport`

## Configuration Files

The main configuration files live under `src/reachy_robotis/config/`.

```text
robotis_devices.yaml          Default device mode, host, user, container, and command allowlist
robotis_connections.yaml      SSH/Docker connection profiles
robotis_actions.yaml          Voice/text trigger to action mappings
robotis_recipes.yaml          Multi-terminal workflow definitions
robotis_product_presets.yaml  Product cards, default connections, and workflow presets
robotis_commands.yaml         Command catalog
robotis_omy_raspberry_pi.yaml OMY-specific settings
robotis_ai_worker_jetson.yaml AI Worker-specific settings
```

The default YAML files include development IP addresses, usernames, and container names. For real devices, save connection settings through the `/robotis` UI or edit the YAML files for your network.

## Product Presets

`robotis_product_presets.yaml` currently defines these product groups:

- `omx`: OMX bringup, MoveIt, GUI, and demo rosbag workflows
- `omy`: OMY AI teleoperation, MoveIt, GUI, and demo rosbag workflows
- `ai_worker`: AI Worker BG2/SG2 workflows
- `hx5_hand`: HX5 Hand container start workflow

Presets provide connection settings, Docker mode, ROS distro/setup paths, and workflow terminal lists. When host/user/auth settings are saved from the `/robotis` UI, the matching connection profile and product state are updated.

## Task, Action, and Recipe

### Task

A task is a step-based robot behavior. One example is `push_box_custom` in `src/reachy_robotis/tasks/omx_tasks.yaml`.

```yaml
{
  "name": "push_box_custom",
  "display_name": "Push Box Custom",
  "triggers": ["push the box", "clear the box"],
  "device": "omx",
  "steps": [
    {"type": "move_l", "params": {"x": 0.18, "y": 0.10, "z": 0.18, "duration": 0.5}},
    {"type": "gripper", "params": {"command": "close"}}
  ]
}
```

Common step types include `move_l`, `gripper`, `wait`, and `say`.

### Action

An action connects user-facing triggers to an execution method. Actions are defined in `robotis_actions.yaml`.

Example execution methods:

- `start_recipe`
- `stop_recipe`
- `run_command`
- `run_manual_task`
- `start_hand_teleop`
- `stop_all`

### Recipe

A recipe runs one or more terminal commands as a workflow. Each terminal entry includes `connection_id`, `command_type`, `command`, `run_mode`, `start_order`, `wait_after_start_sec`, and `stop_command`.

`run_mode` can be foreground or detached. Stop operations run recipe terminals in reverse order.

## Command Execution and Safety

- The web UI and API do not execute arbitrary shell commands directly. They execute allowlisted command keys from YAML or recipe terminal commands.
- `ConnectionRegistry` hides password and key values in API responses.
- Product connection saving verifies that host/user/auth/key_path values round-trip through the UI state.
- Connection testing is split into TCP, SSH, container, and ROS checks.
- Device stop, torque-off, kill, and global stop APIs are available.
- `ROBOTIS_CLI_DRY_RUN` and per-device `dry_run` settings control whether real execution is allowed.

## Camera and Vision

The camera is initialized through `CameraWorker` unless `--no-camera` is passed.

- `--head-tracker yolo`: `reachy_robotis.vision.yolo_head_tracker.HeadTracker`
- `--head-tracker mediapipe`: `reachy_mini_toolbox.vision.HeadTracker`
- `--local-vision`: Initialize the local vision manager
- Realtime vision description uses the configured realtime vision backend when available

`/robotis/camera/stream` returns an MJPEG live stream with detection overlays. `/robotis/camera/snapshot` returns the latest frame as a JPEG with object detection boxes. `/robotis/camera/detections` returns the latest detection result as JSON.

The chat agent also exposes `detect_objects`, a tool that runs the same object detection pipeline on the latest camera frame. It returns labels, confidence scores, bounding boxes, normalized centers, and relative positions so the assistant can answer questions such as what it sees or where an object is located.

## Personality and Tool Loading

`LOCKED_PROFILE` is currently set to `_reachy_robotis_locked_profile`, so the app uses the built-in locked profile instructions and tools by default.

Tool loading flow:

- Read `tools.txt` from the active profile.
- Add system tools defined in `SystemTool`.
- Look for the tool in the profile module first, then fall back to `reachy_robotis.tools`.
- If an external tools directory and `AUTOLOAD_EXTERNAL_TOOLS` are configured, automatically load extra tools.
- Raise an explicit error when an external profile or tool name conflicts with a built-in name.

Representative tool files:

```text
tools/run_robotis_action.py
tools/resolve_robotis_intent.py
tools/list_robotis_actions.py
tools/list_robot_commands.py
tools/list_robot_connections.py
tools/test_robot_connection.py
tools/detect_objects.py
tools/task_status.py
tools/task_cancel.py
tools/move_head.py
tools/head_tracking.py
tools/camera.py
tools/dance.py
```

## Code Structure

```text
src/reachy_robotis/
  main.py                         App and CLI entrypoint
  cli.py                          Task CLI and text-only chat mode
  config.py                       Environment, backend, profile, and tool path settings
  openai_realtime.py              Realtime voice/text handler
  console.py                      Headless LocalStream and settings API
  gradio_personality.py           Gradio personality UI
  headless_personality*.py        Headless personality save/apply API
  camera_worker.py                Reachy camera frame worker
  moves.py                        Reachy movement manager
  audio/                          Speech tapper and head wobbler
  vision/                         Object detector, processors, and YOLO tracker
  tools/                          Function-calling tool implementations
  profiles/                       Built-in locked profile
  config/                         ROBOTIS YAML settings
  tasks/                          Task YAML files
  static/                         Chat/settings frontend
  robotis_interface/
    adapters/                     Device-specific adapters
    core/                         Catalogs, resolver, executor, registry, and session manager
    transports/                   CLI/SSH/Docker/HTTP/WebSocket/mock transports
    web/                          /robotis FastAPI routes and static panel
```

## Tests

Tests live under `tests/`.

```bash
uv run pytest
```

Individual examples:

```bash
uv run pytest tests/test_connection_registry.py
uv run pytest tests/test_openai_realtime.py
uv run pytest tests/tools/test_background_tool_manager.py
uv run pytest tests/vision/test_processors.py
```

Static checks are configured in `pyproject.toml`.

```bash
uv run ruff check src tests
uv run mypy
```

## Current Notes

- This project is an integrated interface for running ROBOTIS device workflows from the Reachy Mini app. It is not intended to be a complete general-purpose multi-robot framework.
- It does not train or deploy a real VLA model. It resolves and executes registered triggers, tasks, actions, recipes, and commands.
- Default device settings include development IP addresses and container names. Update them for your real network.
- The `docs/` directory is not present in the current repository. Old README links to `docs/TASKS.md`, `docs/EXTENDING.md`, and `docs/DEMO_SCRIPT.md` were removed because they no longer match the current implementation.
- Disabling `dry_run` on real robot connections may execute SSH, Docker, ROS, and robot motion commands. Verify physical safety around the devices before running live actions.
