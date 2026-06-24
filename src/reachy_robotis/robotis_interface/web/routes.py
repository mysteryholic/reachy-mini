from __future__ import annotations

import os
import time
import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from reachy_robotis.config import config
from reachy_robotis.secret_utils import openai_key_status
from reachy_robotis.robotis_interface.adapters.omx_adapter import OMXAdapter
from reachy_robotis.robotis_interface.core.schemas import TaskDefinition
from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry
from reachy_robotis.robotis_interface.core.action_executor import ActionExecutor
from reachy_robotis.robotis_interface.core.service import get_robotis_executor
from reachy_robotis.robotis_interface.transports.cli_transport import CLITransport
from reachy_robotis.robotis_interface.transports.connection_transport import ConnectionTransport


def create_robotis_router(
    executor: ActionExecutor | None = None,
    camera_worker: Any = None,
) -> APIRouter:
    """Create the ROBOTIS VLA interface API router."""
    router = APIRouter(prefix="/robotis", tags=["robotis"])
    robotis_executor = executor or get_robotis_executor()
    device_registry = DeviceRegistry()

    # Camera Visualization (section 7): latest detections are cached so the
    # snapshot endpoint runs inference once per frame and the detections list
    # endpoint reuses that result instead of doing a second pass.
    _camera_state: dict[str, Any] = {"detections": [], "ts": 0.0}

    def _app_mode() -> str:
        if os.getenv("SPACE_ID") or os.getenv("SYSTEM") == "spaces":
            return "HF_SPACE_MOCK"
        configs = device_registry.list_devices()
        if any(config.get("mode") not in {"mock"} and not config.get("dry_run", False) for config in configs.values()):
            return "LOCAL_REAL"
        return "LOCAL_MOCK"

    def _transport_label(config: dict[str, Any]) -> str:
        mode = str(config.get("cli_mode") or config.get("mode") or "mock")
        if mode == "ssh_docker":
            return "SSHDockerTransport"
        if mode == "ssh":
            return "SSHTransport"
        if mode == "local_shell":
            return "LocalShellTransport"
        if mode == "mock":
            return "MockTransport"
        if mode == "websocket":
            return "WebSocketTransport"
        return mode

    def _device_title(device: str) -> str:
        return {
            "reachy": "Reachy Mini",
            "omx": "OMX",
            "omy": "OMY Raspberry Pi",
            "ai_worker": "AI Worker Jetson Orin 32GB",
            "mock": "Mock",
        }.get(device, device)

    def _device_flow(device: str, config: dict[str, Any]) -> str:
        mode = str(config.get("mode") or "")
        if device == "omy":
            return "Reachy Mini -> SSH -> Raspberry Pi -> docker exec -> ros2 launch"
        if device == "ai_worker":
            if mode == "ssh_docker":
                return "Reachy Mini -> SSH -> Jetson Orin -> Docker ROS 2 launch"
            return "Reachy Mini -> SSH -> Jetson Orin -> local ROS 2 launch"
        if device == "omx":
            return "Reachy Mini -> ConnectionProfile omx_pc -> SSH -> Docker exec open_manipulator -> ROS 2 OMX CLI command"
        if device == "reachy":
            return "Human voice/chat/UI -> Reachy Mini Conversation App"
        return "Mock adapter demo flow"

    def _action_path(kind: str, device: str) -> str:
        if kind == "task" and device == "omx":
            return "OMXAdapter -> OMX Bridge HTTP -> move_l/gripper/wait sequence"
        if kind == "task" and device == "mock":
            return "MockAdapter -> simulated task steps"
        if device == "omy":
            return "OMYAdapter -> SSHDockerTransport -> docker exec -> ros2 launch"
        if device == "ai_worker":
            config = device_registry.get("ai_worker")
            if config.get("mode") == "ssh_docker":
                return "AIWorkerAdapter -> SSHDockerTransport -> docker exec -> ros2 launch"
            return "AIWorkerAdapter -> SSH/LocalShellTransport -> ROS 2 launch"
        if device == "omx":
            return "ActionExecutor -> ConnectionTransport -> SSHDockerTransport-compatible docker exec -> allowlisted OMX CLI command"
        return f"{device} adapter"

    def _devices_payload() -> list[dict[str, Any]]:
        # The status store is the single source of truth for mode/host/container/
        # online/connection_status. Config only supplies static descriptors
        # (transport label, user, ROS setup paths, command keys, flow text).
        statuses = robotis_executor.status()
        devices = []
        for device, device_config in device_registry.list_devices().items():
            status = statuses.get(device, {})
            devices.append(
                {
                    "id": device,
                    "name": _device_title(device),
                    "target": device_config.get("platform", device),
                    "mode": status.get("mode", device_config.get("mode", "mock")),
                    "configured": status.get("configured", False),
                    "connection_status": status.get("connection_status", "not_checked"),
                    "cli_mode": device_config.get("cli_mode", ""),
                    "transport": _transport_label(device_config),
                    "host": status.get("host", device_config.get("host", "")),
                    "user": device_config.get("user", ""),
                    "container": status.get("container", device_config.get("container_name", "")),
                    "ros_setup_path": device_config.get("ros_setup_path", ""),
                    "ros_setup_paths": device_config.get("ros_setup_paths", []),
                    "connection_id": device_config.get("connection_id", ""),
                    "flow": _device_flow(device, device_config),
                    "commands": sorted((device_config.get("commands") or {}).keys()) if isinstance(device_config.get("commands"), dict) else [],
                    "command_specs": [
                        device_registry.command_spec(device, key)
                        for key in device_registry.command_keys(device)
                    ],
                    "online": status.get("online", False),
                    "active_action": status.get("active_action"),
                    "last_command": status.get("last_message", ""),
                    "last_command_result": robotis_executor.last_command(device),
                    "last_error": status.get("last_error", ""),
                    "log": status.get("log", []),
                }
            )
        return devices

    def _actions_payload() -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        statuses = robotis_executor.status()
        if robotis_executor.action_catalog is not None:
            for action in robotis_executor.action_catalog.list_actions():
                command_key = action.run.get("command_key") if isinstance(action.run, dict) else None
                actions.append(
                    {
                        **action.to_mapping(),
                        "kind": "action",
                        "command_key": command_key,
                        "path": _action_path("action", action.device),
                        "status": "running" if statuses.get(action.device, {}).get("active_action") == action.name else "idle",
                    }
                )
        for task in robotis_executor.task_catalog.list_tasks():
            actions.append(
                {
                    **task.to_mapping(),
                    "kind": "task",
                    "path": _action_path("task", task.device),
                    "status": "running" if statuses.get(task.device, {}).get("active_action") == task.name else "idle",
                }
            )
        for command in robotis_executor.command_catalog.list_commands():
            actions.append(
                {
                    **command.to_mapping(),
                    "kind": "command",
                    "path": _action_path("command", command.device),
                    "status": "running" if statuses.get(command.device, {}).get("active_action") == command.name else "idle",
                }
            )
        return actions

    def _recipes_payload() -> list[dict[str, Any]]:
        if robotis_executor.recipe_catalog is None:
            return []
        return [recipe.to_mapping() for recipe in robotis_executor.recipe_catalog.list_recipes()]

    def _summary_payload() -> dict[str, Any]:
        statuses = robotis_executor.status()
        active = [
            status.get("active_action")
            for status in statuses.values()
            if status.get("active_action")
        ]
        return {
            "ok": True,
            "app": {
                "title": "Robot Action Interface",
                "summary": "Reachy Mini listens to human commands, resolves them into registered robot actions, and executes them through OMX, OMY, AI Worker, or Mock adapters.",
                "mode": _app_mode(),
                "pipeline": ["Human Voice / Chat / UI", "Reachy Mini Conversation App", "Intent Resolver", "Action Catalog", "Action Executor", "Device Adapter", "Robot Action"],
                "active_action": ", ".join(active) if active else "idle",
                **robotis_executor.ui_snapshot(),
            },
            "devices": _devices_payload(),
            "actions": _actions_payload(),
            "recipes": _recipes_payload(),
            "tasks": [task.to_mapping() for task in robotis_executor.task_catalog.list_tasks()],
            "sessions": robotis_executor.terminal_session_manager.sessions_snapshot()
            if robotis_executor.terminal_session_manager is not None
            else [],
            "connections": [
                profile.to_public_mapping()
                for profile in robotis_executor.connection_registry.list_connections().values()
            ] if robotis_executor.connection_registry else [],
        }

    async def _refresh_device_statuses() -> None:
        """Probe cheap live connectivity (OMX HTTP bridge) for hot endpoints.

        Only OMX is probed here because its HTTP bridge check is fast and its
        online state drives the dashboard. SSH devices (omy/ai_worker) are
        intentionally left ``not_checked`` until the user runs an explicit
        connection test, so we never block /status or /health on a 5s SSH dial.
        """
        adapter = robotis_executor.adapters.get("omx")
        if adapter is None:
            return
        try:
            await adapter.probe()
        except Exception:
            pass

    def _voice_status() -> str:
        return "enabled" if (config.OPENAI_API_KEY and str(config.OPENAI_API_KEY).strip()) else "disabled"

    def _reload_editable_config() -> None:
        """Reload user-editable connection, recipe, and task files from disk."""
        if robotis_executor.connection_registry is not None:
            robotis_executor.connection_registry.reload()
        if robotis_executor.recipe_catalog is not None:
            robotis_executor.recipe_catalog.reload()
        robotis_executor.task_catalog.reload()

    def _health_payload() -> dict[str, Any]:
        statuses = robotis_executor.status()

        def _device_health(device_id: str) -> str:
            status = statuses.get(device_id, {})
            mode = str(status.get("mode") or "mock")
            if device_id == "omx":
                return "online" if status.get("online") else "offline"
            # Remote ros2 devices: report configured transport mode.
            return mode

        return {
            "ok": True,
            "app": "reachy_robotis",
            "robotis_status": "running",
            "voice_status": _voice_status(),
            "openai_key_status": openai_key_status(config.OPENAI_API_KEY),
            "devices": {
                "omx": _device_health("omx"),
                "omy": _device_health("omy"),
                "ai_worker": _device_health("ai_worker"),
            },
        }

    @router.get("/health")
    async def health() -> dict[str, Any]:
        """Liveness/health summary. Must respond even without an OpenAI key."""
        try:
            await _refresh_device_statuses()
        except Exception:
            pass
        return _health_payload()

    @router.get("", response_class=HTMLResponse)
    async def panel() -> str:
        return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Robot CLI Console</title>
    <link rel="stylesheet" href="/robotis/static/robotis_panel.css?v=20260624-camera-viz" />
  </head>
  <body>
    <main class="shell compact-shell">
      <header class="compact-header">
        <div>
          <p class="eyebrow">Reachy Mini</p>
          <h1>Conversation-driven CLI Robot Interface</h1>
          <p class="subtitle">Talk to Reachy Mini, resolve requests into saved robot CLI recipes, deliver them over SSH, and inspect terminal logs.</p>
        </div>
        <div class="hero-actions">
          <button id="refresh" type="button">Refresh</button>
          <button id="global-stop" type="button" class="danger">Stop All</button>
        </div>
      </header>

      <section class="console-section primary-section">
        <h2>1. Conversation Control</h2>
        <div class="conversation-layout">
          <div class="stack">
            <label>Say what you want the robot to do<textarea id="conversation-input" rows="3">start OMX MoveIt</textarea></label>
            <div class="row">
              <button id="resolve-conversation" type="button" class="secondary">Resolve</button>
              <button id="run-conversation" type="button">Resolve and Run</button>
              <a class="button-link secondary" href="/chat">Open Chat / Voice</a>
            </div>
            <pre id="conversation-result"></pre>
          </div>
          <div>
            <h3>Conversation Transcript</h3>
            <div id="conversation-log" class="conversation-log"></div>
          </div>
        </div>
      </section>

      <section class="console-section">
        <h2>2. SSH Delivery Setup</h2>
        <p class="muted">Save how Reachy Mini reaches each robot control PC. Tests use the currently edited values.</p>
        <div id="connection-list" class="compact-list"></div>
        <form id="connection-editor" class="compact-form">
          <label>Connection ID<input name="connection_id" value="omx_pc" /></label>
          <label>Host<input name="host" value="192.168.60.74" /></label>
          <label>Port<input name="port" value="22" /></label>
          <label>User<input name="user" value="robotis" /></label>
          <label>Transport<select name="transport"><option>ssh_docker</option><option>ssh</option></select></label>
          <label>Auth<select name="auth_method"><option>ssh_key</option><option>password_env</option></select></label>
          <label>SSH key<input name="key_path" value="~/.ssh/id_ed25519" /></label>
          <label>Password env<input name="password_env" value="OMX_SSH_PASSWORD" /></label>
          <label>Working dir<input name="working_dir" value="~/ros2_ws" /></label>
          <label>Container<input name="container_name" value="open_manipulator" /></label>
          <label>ROS setup<textarea name="ros_setup" rows="2">source /opt/ros/jazzy/setup.bash
source /root/ros2_ws/install/setup.bash</textarea></label>
          <input name="display_name" value="OMX Control PC" hidden />
          <input name="container_mode" value="docker_exec" hidden />
          <input name="exec_shell" value="bash -lc" hidden />
          <input name="ros_distro" value="jazzy" hidden />
          <div class="row">
            <button id="save-connection" type="button">Save</button>
            <button id="test-edited-ssh" type="button" class="secondary">Test SSH</button>
            <button id="test-edited-container" type="button" class="secondary">Test Container</button>
            <button id="test-edited-ros" type="button" class="secondary">Test ROS</button>
          </div>
        </form>
        <pre id="connection-result"></pre>
      </section>

      <section class="console-section">
        <h2>3. Command Recipe</h2>
        <p class="muted">Build the terminal plan that will run on the saved SSH connection. Use one row per terminal command.</p>
        <div class="run-bar">
          <label>Robot<select id="quick-robot"></select></label>
          <label>Saved recipe<select id="quick-recipe"></select></label>
          <button id="quick-run" type="button">Run</button>
          <button id="quick-stop" type="button" class="danger">Stop</button>
        </div>
        <form id="recipe-editor" class="compact-recipe">
          <label>Recipe ID<input name="recipe_id" value="custom_omx_recipe" /></label>
          <label>Name<input name="display_name" value="Custom OMX Recipe" /></label>
          <label>Device<select name="device"><option>omx</option><option>omy</option><option>ai_worker</option></select></label>
          <label>Description<input name="description" value="Run a custom multi-terminal robot CLI workflow." /></label>
          <label>Triggers<textarea name="triggers" rows="2">start custom OMX recipe</textarea></label>
          <div class="row">
            <button id="new-recipe" type="button" class="secondary">New Recipe</button>
            <button id="add-recipe-terminal" type="button" class="secondary">Add Terminal</button>
            <button id="save-recipe" type="button">Save Recipe</button>
            <button id="run-edited-recipe" type="button">Run Edited</button>
            <button id="delete-edited-recipe" type="button" class="danger">Delete</button>
          </div>
          <div id="recipe-list" class="compact-list"></div>
          <div id="recipe-terminal-table" class="table-wrap"></div>
        </form>
        <pre id="result"></pre>
      </section>

      <section class="console-section">
        <h2>4. Terminal Sessions / Logs</h2>
        <div id="session-table" class="table-wrap"></div>
        <label>Session<select id="log-session"></select></label>
        <button id="load-session-logs" type="button" class="secondary">Load Logs</button>
        <pre id="log-viewer"></pre>
      </section>

      <section class="console-section">
        <h2>5. OMX Manual Task</h2>
        <form id="task-builder" class="builder-layout">
          <div class="stack">
            <label>Load existing task<select id="task-load-select"></select></label>
            <label>Task name<input name="name" value="custom_omx_task" /></label>
            <label>Name<input name="display_name" value="Custom OMX Task" /></label>
            <label>Trigger<input name="trigger" value="custom task" /></label>
            <div class="row">
              <button id="add-movel" type="button" class="secondary">Add MoveL</button>
              <button id="add-open" type="button" class="secondary">Gripper Open</button>
              <button id="add-close" type="button" class="secondary">Gripper Close</button>
              <button id="add-wait" type="button" class="secondary">Wait</button>
            </div>
            <div id="step-table" class="table-wrap"></div>
            <div class="row">
              <button type="submit">Save Task</button>
              <button id="run-built-task" type="button">Run Task</button>
              <button id="delete-built-task" type="button" class="danger">Delete task</button>
            </div>
          </div>
          <pre id="export-yaml"></pre>
        </form>
      </section>

      <section class="console-section">
        <h2>6. OMX Hand Teleop</h2>
        <p class="muted">Keep this simple for now: start, stop, and watch the session state.</p>
        <div class="row">
          <button id="teleop-start" type="button">Start Teleop</button>
          <button id="teleop-stop" type="button" class="secondary">Stop Teleop</button>
        </div>
        <div id="teleop-status" class="status-panel"></div>
      </section>

      <section class="console-section">
        <h2>7. Camera Visualization</h2>
        <p class="muted">Live camera feed from Reachy Mini with on-frame object detection. Boxes and labels are drawn server-side; the list shows the current detection status.</p>
        <div class="row">
          <button id="camera-start" type="button">Start Visualization</button>
          <button id="camera-stop" type="button" class="secondary">Stop</button>
          <span id="camera-status" class="muted"></span>
        </div>
        <div class="camera-layout">
          <div class="camera-view">
            <img id="camera-frame" alt="Camera feed with object detection" />
          </div>
          <div class="camera-detections">
            <h3>Detections <span id="camera-count" class="badge">0</span></h3>
            <div id="camera-detection-list" class="compact-list"></div>
          </div>
        </div>
      </section>
    </main>
    <script src="/robotis/static/robotis_panel.js?v=20260624-camera-viz"></script>
  </body>
</html>
"""

    @router.get("/status")
    async def status() -> dict[str, Any]:
        await _refresh_device_statuses()
        return {"ok": True, "devices": robotis_executor.status(), "device_details": _devices_payload()}

    @router.get("/actions")
    async def actions() -> dict[str, Any]:
        catalog = robotis_executor.list_actions()
        return {"ok": True, **catalog, "registered_actions": _actions_payload()}

    @router.get("/commands/preview/{device}/{command_key}")
    async def command_preview(device: str, command_key: str) -> dict[str, Any]:
        preview = CLITransport(device, device_registry, robotis_executor.status_store).preview_command(command_key)
        robotis_executor.record_event(f"Command preview requested: {device}:{command_key}")
        return preview

    @router.get("/ui/summary")
    async def ui_summary() -> dict[str, Any]:
        _reload_editable_config()
        return _summary_payload()

    @router.get("/recipes")
    async def list_recipes() -> dict[str, Any]:
        """List user-facing Command Recipes."""
        _reload_editable_config()
        return {"ok": True, "recipes": _recipes_payload()}

    @router.get("/recipes/{recipe_id}")
    async def get_recipe(recipe_id: str) -> dict[str, Any]:
        """Return one Command Recipe."""
        _reload_editable_config()
        catalog = robotis_executor.recipe_catalog
        if catalog is None:
            return {"ok": False, "error": "recipe_catalog_unavailable"}
        recipe = catalog.get(recipe_id)
        if recipe is None:
            return {"ok": False, "error": "unknown_recipe", "recipe_id": recipe_id}
        return {"ok": True, "recipe": recipe.to_mapping()}

    @router.post("/recipes/{recipe_id}")
    async def save_recipe(recipe_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Create or update one Command Recipe."""
        catalog = robotis_executor.recipe_catalog
        if catalog is None:
            return {"ok": False, "error": "recipe_catalog_unavailable"}
        recipe_payload = payload.get("recipe") if isinstance(payload.get("recipe"), dict) else payload
        try:
            recipe = catalog.from_payload(recipe_id, dict(recipe_payload))
            catalog.add_or_update(recipe, persist=True)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": "invalid_recipe", "message": str(exc)}
        robotis_executor.record_event(f"Recipe saved: {recipe_id}")
        return {"ok": True, "recipe": recipe.to_mapping()}

    @router.delete("/recipes/{recipe_id}")
    async def delete_recipe(recipe_id: str) -> dict[str, Any]:
        """Delete one Command Recipe."""
        catalog = robotis_executor.recipe_catalog
        if catalog is None:
            return {"ok": False, "error": "recipe_catalog_unavailable"}
        removed = catalog.delete(recipe_id, persist=True)
        if not removed:
            return {"ok": False, "error": "unknown_recipe", "recipe_id": recipe_id}
        robotis_executor.record_event(f"Recipe deleted: {recipe_id}")
        return {"ok": True, "deleted": recipe_id}

    @router.post("/recipes/{recipe_id}/run")
    async def run_recipe(recipe_id: str) -> dict[str, Any]:
        """Start a Command Recipe in terminal start_order."""
        robotis_executor.record_event(f"Recipe run requested: {recipe_id}")
        return (await robotis_executor.start_recipe(recipe_id)).to_mapping()

    @router.post("/recipes/{recipe_id}/stop")
    async def stop_recipe(recipe_id: str) -> dict[str, Any]:
        """Stop a Command Recipe in reverse terminal start_order."""
        robotis_executor.record_event(f"Recipe stop requested: {recipe_id}")
        return (await robotis_executor.stop_recipe(recipe_id)).to_mapping()

    @router.get("/sessions")
    async def list_sessions() -> dict[str, Any]:
        """List tracked terminal sessions."""
        manager = robotis_executor.terminal_session_manager
        if manager is None:
            return {"ok": False, "error": "terminal_session_manager_unavailable", "sessions": []}
        return await manager.list_sessions()

    @router.get("/sessions/{session_id}")
    async def get_session(session_id: str) -> dict[str, Any]:
        """Return one terminal session."""
        manager = robotis_executor.terminal_session_manager
        if manager is None:
            return {"ok": False, "error": "terminal_session_manager_unavailable"}
        return await manager.get_session(session_id)

    @router.post("/sessions/{session_id}/stop")
    async def stop_session(session_id: str) -> dict[str, Any]:
        """Stop one terminal session."""
        manager = robotis_executor.terminal_session_manager
        if manager is None:
            return {"ok": False, "error": "terminal_session_manager_unavailable"}
        robotis_executor.record_event(f"Terminal session stop requested: {session_id}")
        return await manager.stop_terminal(session_id)

    @router.get("/sessions/{session_id}/logs")
    async def session_logs(session_id: str, lines: int = 100) -> dict[str, Any]:
        """Return captured stdout/stderr tails for one terminal session."""
        manager = robotis_executor.terminal_session_manager
        if manager is None:
            return {"ok": False, "error": "terminal_session_manager_unavailable"}
        return await manager.get_session_logs(session_id, lines=lines)

    @router.post("/resolve")
    async def resolve(payload: dict[str, Any]) -> dict[str, Any]:
        return await intent_resolve(payload)

    @router.post("/intent/resolve")
    async def intent_resolve(payload: dict[str, Any]) -> dict[str, Any]:
        text = str(payload.get("text", ""))
        resolved = robotis_executor.resolve(text)
        return {**resolved, "action": resolved.get("name"), "execution_path": _execution_path_for_resolved(resolved)}

    @router.post("/run")
    async def run(payload: dict[str, Any]) -> dict[str, Any]:
        return await actions_run(payload)

    @router.post("/actions/run")
    async def actions_run(payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", ""))
        kind = payload.get("kind")
        if kind:
            result = await robotis_executor.run_action(str(kind), name)
        else:
            result = await robotis_executor.run_resolved_text(name)
        result_payload = result.to_mapping()
        return result_payload

    @router.post("/stop")
    async def stop(payload: dict[str, Any]) -> dict[str, Any]:
        device = payload.get("device")
        robotis_executor.record_event(f"Soft Stop requested: {device or 'all devices'}")
        result = (await robotis_executor.stop(str(device) if device else None)).to_mapping()
        return result

    @router.post("/devices/{device_id}/stop")
    async def device_stop(device_id: str) -> dict[str, Any]:
        """Soft stop a specific device."""
        robotis_executor.record_event(f"Device Stop requested: {device_id}")
        result = (await robotis_executor.stop(device_id)).to_mapping()
        return result

    @router.post("/devices/{device_id}/torque-off")
    async def device_torque_off(device_id: str) -> dict[str, Any]:
        """Turn off torque for a specific device."""
        robotis_executor.record_event(f"Device Torque Off requested: {device_id}")
        result = (await robotis_executor.torque_off(device_id)).to_mapping()
        return result

    @router.post("/devices/{device_id}/kill")
    async def device_kill(device_id: str) -> dict[str, Any]:
        """Force kill processes for a specific device."""
        robotis_executor.record_event(f"Device Kill requested: {device_id}")
        result = (await robotis_executor.kill_processes(device_id)).to_mapping()
        return result

    @router.post("/actions/cancel")
    async def cancel_action(payload: dict[str, Any]) -> dict[str, Any]:
        """Cancel active action."""
        device = payload.get("device")
        robotis_executor.record_event(f"Cancel active action requested: {device or 'all devices'}")
        result = (await robotis_executor.cancel_active_action(str(device) if device else None)).to_mapping()
        return result

    # ---- Generic CLI command interface (Connection Profile driven) ----
    @router.get("/connections")
    async def list_connections() -> dict[str, Any]:
        """List connection profiles (no secrets)."""
        _reload_editable_config()
        cr = robotis_executor.connection_registry
        if cr is None:
            return {"ok": False, "error": "connection_registry_unavailable", "connections": []}
        return {"ok": True, "connections": [p.to_public_mapping() for p in cr.list_connections().values()]}

    @router.get("/connections/{connection_id}")
    async def get_connection(connection_id: str) -> dict[str, Any]:
        """Return one connection profile without secrets."""
        _reload_editable_config()
        cr = robotis_executor.connection_registry
        if cr is None:
            return {"ok": False, "error": "connection_registry_unavailable"}
        profile = cr.get(connection_id)
        if profile is None:
            return {"ok": False, "error": "unknown_connection", "connection_id": connection_id}
        return {"ok": True, "connection": profile.to_public_mapping()}

    @router.post("/connections/{connection_id}")
    async def save_connection(connection_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist one connection profile. Secrets must remain in environment variables."""
        cr = robotis_executor.connection_registry
        if cr is None:
            return {"ok": False, "error": "connection_registry_unavailable"}
        profile = cr.save_connection(connection_id, payload)
        robotis_executor.record_event(f"Connection profile saved: {connection_id}")
        return {"ok": True, "connection": profile.to_public_mapping()}

    @router.post("/connections/{connection_id}/test")
    async def test_connection(connection_id: str) -> dict[str, Any]:
        """Test a connection profile. Step 1 = TCP reachability (fast, safe)."""
        return await test_connection_tcp(connection_id)

    @router.post("/connections/{connection_id}/test/tcp")
    async def test_connection_tcp(connection_id: str) -> dict[str, Any]:
        """Test TCP reachability for a connection profile."""
        cr = robotis_executor.connection_registry
        if cr is None:
            return {"ok": False, "error": "connection_registry_unavailable"}
        robotis_executor.record_event(f"Connection test requested: {connection_id}")
        result = await asyncio.to_thread(cr.test_tcp, connection_id)
        return {"ok": bool(result.get("ok")), **result}

    async def _connection_command_test(connection_id: str, step: str, command: str, command_type: str) -> dict[str, Any]:
        cr = robotis_executor.connection_registry
        if cr is None:
            return {"ok": False, "error": "connection_registry_unavailable", "step": step}
        profile = cr.get(connection_id)
        if profile is None:
            return {"ok": False, "error": "unknown_connection", "step": step, "connection_id": connection_id}
        dry_run = os.getenv("ROBOTIS_CLI_DRY_RUN") == "1"
        result = await ConnectionTransport(profile).async_run_command(command, command_type, "foreground", dry_run=dry_run)
        payload = result.to_mapping()
        payload["step"] = step
        payload["connection_id"] = connection_id
        return payload

    @router.post("/connections/{connection_id}/test/ssh")
    async def test_connection_ssh(connection_id: str) -> dict[str, Any]:
        """Test SSH command assembly/execution for a connection profile."""
        robotis_executor.record_event(f"SSH connection test requested: {connection_id}")
        return await _connection_command_test(connection_id, "ssh", "true", "host")

    @router.post("/connections/{connection_id}/test/container")
    async def test_connection_container(connection_id: str) -> dict[str, Any]:
        """Test container command assembly/execution for a connection profile."""
        robotis_executor.record_event(f"Container connection test requested: {connection_id}")
        return await _connection_command_test(connection_id, "container", "echo container_test", "container")

    @router.post("/connections/{connection_id}/test/ros")
    async def test_connection_ros(connection_id: str) -> dict[str, Any]:
        """Test ROS command assembly/execution for a connection profile."""
        robotis_executor.record_event(f"ROS connection test requested: {connection_id}")
        return await _connection_command_test(connection_id, "ros", "ros2 pkg prefix ros2cli", "container")

    @router.get("/devices/{device_id}/commands")
    async def device_commands(device_id: str) -> dict[str, Any]:
        """List allowlisted command specs for a device."""
        reg = robotis_executor.registry or device_registry
        keys = reg.command_keys(device_id)
        commands = [reg.command_spec(device_id, key) for key in keys]
        return {
            "ok": True,
            "device": device_id,
            "connection_id": reg.connection_id_for(device_id),
            "commands": [c for c in commands if c],
        }

    @router.post("/devices/{device_id}/commands/{command_key}/run")
    async def device_command_run(device_id: str, command_key: str) -> dict[str, Any]:
        """Run one allowlisted command_key on a device (rosbag/bringup/etc.)."""
        robotis_executor.record_event(f"CLI command run: {device_id}:{command_key}")
        result = (await robotis_executor.run_device_command(device_id, command_key)).to_mapping()
        return result

    @router.get("/devices/{device_id}/status")
    async def device_status(device_id: str) -> dict[str, Any]:
        """Live status for one device (probes OMX bridge; reads stored status otherwise)."""
        adapter = robotis_executor.adapters.get(device_id)
        if adapter is not None:
            try:
                await adapter.probe()
            except Exception:
                pass
        status = robotis_executor.status().get(device_id, {})
        return {"ok": True, "device": device_id, "status": status, "last_command": robotis_executor.last_command(device_id)}

    @router.get("/devices/{device_id}/logs")
    async def device_logs(device_id: str) -> dict[str, Any]:
        """Log preview for one device: status log + last CLI command return code/output."""
        status = robotis_executor.status().get(device_id, {})
        return {
            "ok": True,
            "device": device_id,
            "log": status.get("log", []),
            "last_error": status.get("last_error", ""),
            "last_command": robotis_executor.last_command(device_id),
        }

    @router.post("/connect")
    async def connect_robot() -> dict[str, Any]:
        """Connect to robot and enable command execution."""
        robotis_executor.record_event("User requested: Connect to robot")
        result = (await robotis_executor.connect()).to_mapping()
        return result

    @router.post("/disconnect")
    async def disconnect_robot() -> dict[str, Any]:
        """Disconnect from robot and safely stop all motors."""
        robotis_executor.record_event("User requested: Disconnect from robot")
        result = (await robotis_executor.disconnect()).to_mapping()
        return result

    @router.get("/connection/status")
    async def connection_status() -> dict[str, Any]:
        """Get current robot connection status."""
        return {
            "ok": True,
            "connected": robotis_executor.is_connected(),
            "status": "🟢 Connected" if robotis_executor.is_connected() else "🔴 Disconnected",
        }

    @router.post("/tasks")
    async def save_task(payload: dict[str, Any]) -> dict[str, Any]:
        return await tasks_save(payload)

    @router.post("/tasks/save")
    async def tasks_save(payload: dict[str, Any]) -> dict[str, Any]:
        task_payload = payload.get("task")
        if not isinstance(task_payload, dict):
            return {"ok": False, "error": "invalid_task_payload"}
        task = TaskDefinition.from_mapping(task_payload)
        robotis_executor.task_catalog.add_or_update(task)
        robotis_executor.task_catalog.save()
        robotis_executor.record_event(f"Task saved: {task.name} triggers={', '.join(task.triggers)}")
        return {"ok": True, "task": task.to_mapping()}

    @router.get("/tasks/export")
    async def export_tasks() -> dict[str, Any]:
        return {"ok": True, **robotis_executor.task_catalog.export()}

    @router.delete("/tasks/{name}")
    async def delete_task(name: str) -> dict[str, Any]:
        return await tasks_delete({"name": name})

    @router.post("/tasks/delete")
    async def tasks_delete(payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", ""))
        removed = robotis_executor.task_catalog.delete(name, persist=True)
        if not removed:
            return {"ok": False, "error": "unknown_task", "name": name}
        robotis_executor.record_event(f"Task deleted: {name}")
        return {"ok": True, "deleted": name}

    @router.get("/logs")
    async def logs() -> dict[str, Any]:
        return {
            "ok": True,
            "timeline": robotis_executor.ui_snapshot()["timeline"],
            "devices": {device["id"]: device.get("log", []) for device in _devices_payload()},
        }

    def _execution_path_for_resolved(resolved: dict[str, Any]) -> str:
        kind = resolved.get("kind")
        name = resolved.get("name")
        if kind == "task":
            task = robotis_executor.task_catalog.get(str(name))
            return _action_path("task", task.device) if task else ""
        if kind == "command":
            command = robotis_executor.command_catalog.get(str(name))
            return _action_path("command", command.device) if command else ""
        if kind == "action" and robotis_executor.action_catalog is not None:
            action = robotis_executor.action_catalog.get(str(name))
            return _action_path("action", action.device) if action else ""
        return ""

    @router.websocket("/ws")
    async def robotis_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                await websocket.send_json({"type": "robotis.update", **_summary_payload(), "logs": (await logs())})
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            return

    @router.websocket("/omx/teleop")
    async def omx_teleop(websocket: WebSocket) -> None:
        await websocket.accept()
        adapter = robotis_executor.adapters.get("omx")
        if not isinstance(adapter, OMXAdapter):
            await websocket.send_json({"ok": False, "error": "omx_adapter_missing"})
            await websocket.close()
            return
        session_id = websocket.query_params.get("session_id", "web-teleop")
        await websocket.send_json((await adapter.start_teleop(session_id)).to_mapping())
        try:
            while True:
                payload = await websocket.receive_json()
                if payload.get("type") == "omx.teleop.stop":
                    await websocket.send_json((await adapter.stop_teleop()).to_mapping())
                    continue
                await websocket.send_json((await adapter.handle_teleop_target(dict(payload))).to_mapping())
        except WebSocketDisconnect:
            await adapter.stop_teleop()

    @router.websocket("/omx/task")
    async def omx_task(websocket: WebSocket) -> None:
        await websocket.accept()
        adapter = robotis_executor.adapters.get("omx")
        if not isinstance(adapter, OMXAdapter):
            await websocket.send_json({"ok": False, "error": "omx_adapter_missing"})
            await websocket.close()
            return
        try:
            while True:
                payload = await websocket.receive_json()
                await websocket.send_json((await adapter.handle_task_message(dict(payload))).to_mapping())
        except WebSocketDisconnect:
            return

    # ----- Section 7: Camera Visualization (live feed + object detection) -----

    def _run_detection(frame: Any) -> list[dict[str, Any]]:
        """Detect objects on a frame and cache the result for the list view."""
        from reachy_robotis.vision.object_detector import get_object_detector

        detections = get_object_detector().detect(frame)
        _camera_state["detections"] = detections
        _camera_state["ts"] = time.monotonic()
        return detections

    @router.get("/camera/status")
    async def camera_status() -> dict[str, Any]:
        """Report whether the camera feed and object detector are available."""
        from reachy_robotis.vision.object_detector import get_object_detector

        has_frame = bool(camera_worker is not None and camera_worker.get_latest_frame() is not None)
        detector = get_object_detector()
        detection_available = detector.available
        return {
            "ok": True,
            "camera_available": camera_worker is not None,
            "frame_available": has_frame,
            "detection_available": detection_available,
            "detection_error": None if detection_available else detector.error,
        }

    @router.get("/camera/snapshot")
    async def camera_snapshot() -> Response:
        """Return the latest camera frame as JPEG with detection boxes drawn."""
        import cv2

        from reachy_robotis.vision.object_detector import get_object_detector

        if camera_worker is None:
            return Response(status_code=503, content=b"camera worker not running")
        frame = await asyncio.to_thread(camera_worker.get_latest_frame)
        if frame is None:
            return Response(status_code=503, content=b"no frame available")

        detections = await asyncio.to_thread(_run_detection, frame)
        annotated = await asyncio.to_thread(get_object_detector().annotate, frame, detections)
        ok, buffer = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            return Response(status_code=500, content=b"failed to encode frame")
        return Response(
            content=buffer.tobytes(),
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/camera/detections")
    async def camera_detections() -> JSONResponse:
        """Return the detections from the most recent snapshot inference."""
        from reachy_robotis.vision.object_detector import get_object_detector

        detector = get_object_detector()
        detections = _camera_state["detections"]
        counts: dict[str, int] = {}
        for det in detections:
            counts[det["label"]] = counts.get(det["label"], 0) + 1
        return JSONResponse(
            {
                "ok": True,
                "detection_available": detector.available,
                "detection_error": None if detector.available else detector.error,
                "count": len(detections),
                "counts": counts,
                "detections": detections,
            }
        )

    return router


def mount_robotis_routes(
    app: FastAPI,
    executor: ActionExecutor | None = None,
    camera_worker: Any = None,
) -> None:
    """Mount ROBOTIS API routes and panel assets on a FastAPI app."""
    static_dir = Path(__file__).parent / "static"
    try:
        app.mount("/robotis/static", StaticFiles(directory=str(static_dir)), name="robotis_static")
    except Exception:
        pass
    app.include_router(create_robotis_router(executor, camera_worker=camera_worker))
