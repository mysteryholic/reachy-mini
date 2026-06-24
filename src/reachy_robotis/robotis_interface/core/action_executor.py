from __future__ import annotations

import os
import asyncio
from typing import Any
from time import strftime
from dataclasses import replace

from reachy_robotis.robotis_interface.adapters.base import RobotAdapter
from reachy_robotis.robotis_interface.core.schemas import ActionResult
from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog
from reachy_robotis.robotis_interface.core.status_store import StatusStore
from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.command_catalog import CommandCatalog
from reachy_robotis.robotis_interface.core.intent_resolver import IntentResolver
from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry
from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.transports.connection_transport import ConnectionTransport
from reachy_robotis.robotis_interface.core.terminal_session_manager import TerminalSessionManager


class ActionExecutor:
    """Validate and execute registered tasks/commands through device adapters."""

    def __init__(
        self,
        *,
        task_catalog: TaskCatalog,
        command_catalog: CommandCatalog,
        resolver: IntentResolver,
        adapters: dict[str, RobotAdapter],
        status_store: StatusStore,
        registry: DeviceRegistry | None = None,
        connection_registry: ConnectionRegistry | None = None,
        action_catalog: ActionCatalog | None = None,
        recipe_catalog: RecipeCatalog | None = None,
        terminal_session_manager: TerminalSessionManager | None = None,
    ) -> None:
        self.task_catalog = task_catalog
        self.command_catalog = command_catalog
        self.resolver = resolver
        self.adapters = adapters
        self.status_store = status_store
        self.registry = registry
        self.connection_registry = connection_registry
        self.action_catalog = action_catalog
        self.recipe_catalog = recipe_catalog
        self.terminal_session_manager = terminal_session_manager
        self._last_command: dict[str, dict[str, Any]] = {}
        self._stop_lock = asyncio.Lock()
        self._connected = False
        self._ui_state: dict[str, Any] = {
            "last_voice_command": "",
            "last_resolved_action": "",
            "last_execution_result": "",
            "last_execution_ok": None,
            "timeline": [],
            "connected": False,
        }

    def _timeline(self, message: str) -> None:
        entry = {"at": strftime("%H:%M:%S"), "message": message}
        self._ui_state["timeline"].append(entry)
        self._ui_state["timeline"] = self._ui_state["timeline"][-80:]

    def ui_snapshot(self) -> dict[str, Any]:
        return {
            **self._ui_state,
            "timeline": list(self._ui_state["timeline"]),
        }

    def record_event(self, message: str) -> None:
        self._timeline(message)

    def list_actions(self) -> dict[str, Any]:
        return {
            "actions": [action.to_mapping() for action in self.action_catalog.list_actions()] if self.action_catalog else [],
            "tasks": [task.to_mapping() for task in self.task_catalog.list_tasks()],
            "commands": [command.to_mapping() for command in self.command_catalog.list_commands()],
            "recipes": [recipe.to_mapping() for recipe in self.recipe_catalog.list_recipes()] if self.recipe_catalog else [],
        }

    def resolve(self, text: str) -> dict[str, Any]:
        resolved = self.resolver.resolve(text).to_mapping()
        self._ui_state["last_voice_command"] = text
        self._ui_state["last_resolved_action"] = resolved.get("name", resolved.get("error", ""))
        self._timeline(f'User said: "{text}"')
        if resolved.get("ok"):
            self._timeline(f"Intent resolved: {resolved.get('kind')}:{resolved.get('name')}")
        else:
            self._timeline(f"Intent unresolved: {resolved.get('error')}")
        return resolved

    async def run_resolved_text(self, text: str) -> ActionResult:
        """Resolve a spoken/typed phrase to a trigger and run it in one shot."""
        resolved = self.resolve(text)
        if not resolved.get("ok") or resolved.get("kind") is None or resolved.get("name") is None:
            message = f"No registered action matched the phrase '{text}'."
            result = ActionResult(
                ok=False,
                error=str(resolved.get("error") or "no_match"),
                message=message,
                data={"reply": message, "matched_text": text},
            )
            self._ui_state["last_execution_result"] = result.message or result.error
            self._ui_state["last_execution_ok"] = False
            return result
        kind = str(resolved["kind"])
        name = str(resolved["name"])
        matched_trigger = str(resolved.get("matched_trigger") or "")
        result = await self.run_action(kind, name)
        reply = result.message or (f"Running '{name}'." if result.ok else f"Could not run '{name}'.")
        return replace(
            result,
            data={
                **(result.data or {}),
                "reply": reply,
                "matched_text": text,
                "matched_trigger": matched_trigger,
                "resolved_kind": kind,
                "resolved_name": name,
            },
        )

    async def run_action(self, kind: str, name: str) -> ActionResult:
        self._timeline(f"Run requested: {kind}:{name}")
        result: ActionResult
        if kind == "action":
            result = await self.run_action_by_name(name)
            self._record_result(result)
            return result

        if kind == "task":
            task = self.task_catalog.get(name)
            if task is None:
                result = ActionResult(ok=False, kind="task", name=name, error="unknown_task", message="Unregistered task.")
                self._record_result(result)
                return result
            adapter = self.adapters.get(task.device)
            if adapter is None:
                result = ActionResult(ok=False, kind="task", name=name, error="unknown_device", message=f"No adapter for {task.device}.")
                self._record_result(result)
                return result
            result = await adapter.run_task(task)
            self._record_result(result)
            return result

        if kind == "command":
            command = self.command_catalog.get(name)
            if command is None:
                result = ActionResult(ok=False, kind="command", name=name, error="unknown_command", message="Unregistered command.")
                self._record_result(result)
                return result
            adapter = self.adapters.get(command.device)
            if adapter is None:
                result = ActionResult(ok=False, kind="command", name=name, error="unknown_device", message=f"No adapter for {command.device}.")
                self._record_result(result)
                return result
            result = await adapter.run_command(command)
            self._record_result(result)
            return result

        if kind == "recipe":
            result = await self.start_recipe(name)
            self._record_result(result)
            return result

        result = ActionResult(ok=False, error="invalid_kind", message="kind must be action, task, command, or recipe.")
        self._record_result(result)
        return result

    def _record_result(self, result: ActionResult) -> None:
        payload = result.to_mapping()
        self._ui_state["last_execution_result"] = payload.get("message") or payload.get("error") or ""
        self._ui_state["last_execution_ok"] = result.ok
        self._timeline(f"Result: {'ok' if result.ok else 'failed'} {payload.get('name') or ''} {payload.get('error') or payload.get('message')}")

    async def run_action_by_name(self, name: str) -> ActionResult:
        """Dispatch a registered ActionCatalog entry by name (run.method)."""
        action = self.action_catalog.get(name) if self.action_catalog else None
        if action is None:
            return ActionResult(ok=False, name=name, error="unknown_action", message=f"Unregistered action: {name}")
        method = str(action.run.get("method") or "")
        if method == "start_recipe":
            return await self.start_recipe(str(action.run.get("recipe_id") or action.name))
        if method == "stop_recipe":
            return await self.stop_recipe(str(action.run.get("recipe_id") or action.name))
        if method == "run_command":
            return await self.run_device_command(action.device, str(action.run.get("command_key") or ""))
        if method == "stop_all":
            return await self.stop(None)
        if method == "run_manual_task":
            return await self.run_action("task", str(action.run.get("task_name") or ""))
        if method == "start_hand_teleop":
            adapter = self.adapters.get(action.device)
            if adapter is not None and hasattr(adapter, "start_teleop"):
                return await adapter.start_teleop("action-invoked")  # type: ignore[attr-defined]
            return ActionResult(ok=False, name=name, error="teleop_unsupported", message=f"{action.device} does not support teleop.")
        return ActionResult(ok=False, name=name, error="unknown_run_method", message=f"Unknown run.method: {method}")

    async def start_recipe(self, recipe_id: str) -> ActionResult:
        if self.terminal_session_manager is None:
            return ActionResult(ok=False, kind="recipe", name=recipe_id, error="recipe_manager_unavailable", message="Recipe manager is not configured.")
        dry_run_env = os.getenv("ROBOTIS_CLI_DRY_RUN")
        dry_run = dry_run_env != "0" if dry_run_env is not None else False
        result = await self.terminal_session_manager.start_recipe(recipe_id, dry_run=dry_run)
        ok = bool(result.get("ok"))
        self._timeline(f"Recipe start: {recipe_id} {'ok' if ok else 'failed'}")
        return ActionResult(
            ok=ok,
            kind="recipe",
            name=recipe_id,
            error=None if ok else str(result.get("error") or "recipe_failed"),
            message=str(result.get("message") or ("Recipe started" if ok else "Recipe failed")),
            data=result,
        )

    async def stop_recipe(self, recipe_id: str) -> ActionResult:
        if self.terminal_session_manager is None:
            return ActionResult(ok=False, kind="recipe", name=recipe_id, error="recipe_manager_unavailable", message="Recipe manager is not configured.")
        dry_run_env = os.getenv("ROBOTIS_CLI_DRY_RUN")
        dry_run = dry_run_env != "0" if dry_run_env is not None else False
        result = await self.terminal_session_manager.stop_recipe(recipe_id, dry_run=dry_run)
        ok = bool(result.get("ok"))
        self._timeline(f"Recipe stop: {recipe_id} {'ok' if ok else 'failed'}")
        return ActionResult(
            ok=ok,
            kind="recipe",
            name=recipe_id,
            error=None if ok else str(result.get("error") or "recipe_stop_failed"),
            message="Recipe stopped" if ok else "Recipe stop failed",
            data=result,
        )

    async def run_device_command(self, device: str, command_key: str) -> ActionResult:
        """Run one allowlisted command_key on a device via its ConnectionProfile."""
        if self.registry is None or self.connection_registry is None:
            return ActionResult(ok=False, error="generic_cli_unavailable", message="The generic CLI interface is not configured.")
        spec = self.registry.command_spec(device, command_key)
        if spec is None or not spec["command"]:
            return ActionResult(
                ok=False, kind="command", name=command_key, error="command_not_allowlisted",
                message=f"{device}:{command_key} is not in the allowlist.",
            )
        connection_id = self.registry.connection_id_for(device)
        if not connection_id:
            return ActionResult(ok=False, kind="command", name=command_key, error="no_connection_id", message=f"{device} has no connection_id.")
        profile = self.connection_registry.get(connection_id)
        if profile is None:
            return ActionResult(ok=False, kind="command", name=command_key, error="unknown_connection", message=f"Connection profile {connection_id} not found.")

        device_cfg = self.registry.get(device)
        dry_run_env = os.getenv("ROBOTIS_CLI_DRY_RUN")
        dry_run = dry_run_env != "0" if dry_run_env is not None else bool(device_cfg.get("dry_run", True))
        transport = ConnectionTransport(profile)
        self.status_store.update(device, active_action=command_key, message=f"CLI run: {command_key} ({spec['run_mode']})")
        result = await transport.async_run_command(spec["command"], spec["command_type"], spec["run_mode"], dry_run=dry_run)

        data = result.data or {}
        self._last_command[device] = {
            "command_key": command_key,
            "command_type": spec["command_type"],
            "run_mode": spec["run_mode"],
            "return_code": data.get("return_code"),
            "return_meaning": data.get("return_meaning", ""),
            "stdout": data.get("stdout_tail", data.get("output", "")),
            "stderr": data.get("stderr_tail", data.get("error", "")),
            "stdout_tail": data.get("stdout_tail", data.get("output", "")),
            "stderr_tail": data.get("stderr_tail", data.get("error", "")),
            "ok": result.ok,
            "dry_run": bool(data.get("dry_run", False)),
            "built_command": data.get("built_command", ""),
        }
        if result.ok:
            self.status_store.update(device, active_action=None, message=f"CLI ok: {command_key} rc={data.get('return_code')}")
        else:
            self.status_store.update(device, active_action=None, error=str(data.get("error") or result.error), message=f"CLI failed: {command_key}")
        return result

    def last_command(self, device: str) -> dict[str, Any]:
        """Return the last generic CLI command outcome for a device (for /logs)."""
        return dict(self._last_command.get(device, {}))

    def _stop_targets(self, device: str | None) -> list[str]:
        """Pick which devices a stop should touch."""
        if device is not None:
            return [device] if device in self.adapters else []
        statuses = self.status_store.snapshot()
        busy_sessions: set[str] = set()
        if self.terminal_session_manager is not None:
            for session in self.terminal_session_manager.sessions_snapshot():
                if str(session.get("state")) in {"pending", "starting", "running", "unknown"}:
                    busy_sessions.add(str(session.get("device")))
        targets: list[str] = []
        for dev in self.adapters:
            status = statuses.get(dev, {})
            if status.get("online") or status.get("active_action") or dev in busy_sessions:
                targets.append(dev)
        return targets

    async def stop(self, device: str | None = None) -> ActionResult:
        async with self._stop_lock:
            target_devices = self._stop_targets(device)
            recipe_results = []
            if self.recipe_catalog is not None and self.terminal_session_manager is not None:
                for recipe in self.recipe_catalog.list_recipes():
                    active = any(
                        session.get("recipe_id") == recipe.recipe_id
                        and session.get("state") in {"pending", "starting", "running", "unknown", "failed"}
                        for session in self.terminal_session_manager.sessions_snapshot()
                    )
                    if recipe.device in target_devices or (device is None and active):
                        recipe_results.append(await self.terminal_session_manager.stop_recipe(recipe.recipe_id))
            results = [await self.adapters[dev].stop() for dev in target_devices]
            ok = all(result.ok for result in results) and all(result.get("ok") for result in recipe_results)
            result = ActionResult(
                ok=ok,
                message="Soft Stop complete" if ok else "Some devices failed to stop",
                data={
                    "stopped_devices": target_devices,
                    "recipe_results": recipe_results,
                    "results": [result.to_mapping() for result in results],
                },
            )
            self._record_result(result)
            return result

    def status(self) -> dict[str, Any]:
        return self.status_store.snapshot()

    async def connect(self) -> ActionResult:
        """Connect to robot (enable all adapters)."""
        self._connected = True
        self._ui_state["connected"] = True
        self._timeline("Robot connected - ready to receive commands")
        return ActionResult(
            ok=True,
            message="Robot connected. Ready to receive commands.",
        )

    async def disconnect(self) -> ActionResult:
        """Disconnect from robot (disable all adapters and stop motors)."""
        self._connected = False
        self._ui_state["connected"] = False
        async with self._stop_lock:
            results = [await adapter.stop() for adapter in self.adapters.values()]
        ok = all(result.ok for result in results)
        self._timeline("Robot disconnected - all motors released")
        return ActionResult(
            ok=ok,
            message="Robot safely shut down.",
            data={"results": [result.to_mapping() for result in results]},
        )

    def is_connected(self) -> bool:
        """Check if robot is currently connected."""
        return self._connected

    async def torque_off(self, device: str | None = None) -> ActionResult:
        """Turn off robot torque for specified device(s)."""
        async with self._stop_lock:
            targets = [self.adapters[device]] if device and device in self.adapters else list(self.adapters.values())
            results = [await adapter.torque_off() for adapter in targets]
            ok = all(result.ok for result in results)
            result = ActionResult(
                ok=ok,
                message="Torque Off complete" if ok else "Some devices failed torque_off",
                data={"results": [result.to_mapping() for result in results]},
            )
            self._record_result(result)
            return result

    async def kill_processes(self, device: str | None = None) -> ActionResult:
        """Force kill robot processes for specified device(s)."""
        async with self._stop_lock:
            targets = [self.adapters[device]] if device and device in self.adapters else list(self.adapters.values())
            results = [await adapter.kill_processes() for adapter in targets]
            ok = all(result.ok for result in results)
            result = ActionResult(
                ok=ok,
                message="Process Kill complete" if ok else "Some devices failed process kill",
                data={"results": [result.to_mapping() for result in results]},
            )
            self._record_result(result)
            return result

    async def cancel_active_action(self, device: str | None = None) -> ActionResult:
        """Cancel active action on specified device(s)."""
        async with self._stop_lock:
            targets = [self.adapters[device]] if device and device in self.adapters else list(self.adapters.values())
            results = [await adapter.cancel_active_action() for adapter in targets]
            ok = all(result.ok for result in results)
            result = ActionResult(
                ok=ok,
                message="Active action cancel complete" if ok else "Some devices failed to cancel the active action",
                data={"results": [result.to_mapping() for result in results]},
            )
            self._record_result(result)
            return result
