from __future__ import annotations

import time
import asyncio
from typing import Any

from reachy_robotis.robotis_interface.adapters.base import RobotAdapter
from reachy_robotis.robotis_interface.core.schemas import ActionResult, CommandDefinition, TaskDefinition, TaskStep
from reachy_robotis.robotis_interface.core.status_store import StatusStore
from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry
from reachy_robotis.robotis_interface.transports.cli_transport import CLITransport
from reachy_robotis.robotis_interface.transports.omx_bridge_transport import OMXBridgeTransport


class OMXAdapter(RobotAdapter):
    """OMX task and hand-teleop adapter with MVP safety guards."""

    def __init__(self, *, status_store: StatusStore, registry: DeviceRegistry) -> None:
        super().__init__(device="omx", status_store=status_store)
        self.registry = registry
        self.config = registry.get("omx")
        self.mode = str(self.config.get("mode") or "mock")
        self.bridge = OMXBridgeTransport(self.config)
        self.cli = CLITransport("omx", registry, status_store)
        self.stable_preset = self.config.get(
            "stable_preset",
            {"republish_rate": 5, "time_from_start": 0.08, "settle_margin": 0.30},
        )
        self._task_lock = asyncio.Lock()
        self._teleop_lock = asyncio.Lock()
        self._teleop_active = False
        self._active_task: str | None = None
        self._last_button_at = 0.0
        self._latest_teleop_seq = -1
        self._last_teleop_packet_at = 0.0
        host = str(self.config.get("bridge_host") or self.config.get("host") or "")
        container = str(self.config.get("container_name") or "")
        self.status_store.update(
            "omx",
            mode=self.mode,
            host=host,
            container=container,
            configured=bool(host),
            connection_status="not_checked",
            online=False,
        )
        if self._bridge_enabled():
            self._apply_bridge_status(self.bridge.get_status())

    def _apply_bridge_status(self, bridge_status: dict[str, Any]) -> dict[str, Any]:
        """Translate a bridge health result into status fields (single place)."""
        if self._bridge_ok(bridge_status):
            self.status_store.update(
                "omx",
                online=True,
                connection_status="online",
                error="",
                message=f"OMX bridge online: {self.bridge.url}",
            )
        else:
            self.status_store.update(
                "omx",
                online=False,
                connection_status="offline",
                error=str(bridge_status.get("error") or bridge_status),
                message=f"OMX bridge offline: {self.bridge.url}",
            )
        return bridge_status

    async def probe(self) -> dict[str, Any]:
        """Live-check the OMX HTTP bridge and update status immediately."""
        if not self._bridge_enabled():
            self.status_store.update("omx", connection_status="not_checked", online=False)
            return {"ok": False, "device": "omx", "checked": False, "error": "bridge_not_enabled"}
        bridge_status = await asyncio.to_thread(self.bridge.get_status)
        self._apply_bridge_status(bridge_status)
        return {"ok": self._bridge_ok(bridge_status), "device": "omx", "checked": True, "bridge_status": bridge_status}

    async def run_command(self, command: CommandDefinition) -> ActionResult:
        result = await self.cli.run(command)
        if command.command_key == "bringup" and result.ok:
            self.status_store.update("omx", online=False, connection_status="checking", message="OMX bridge bringup command accepted; waiting for HTTP/WebSocket bridge")
            bridge_status = await asyncio.to_thread(self.bridge.wait_until_online, timeout_s=18.0, interval_s=0.5)
            if self._bridge_ok(bridge_status):
                self.status_store.update("omx", online=True, connection_status="online", error="", message=f"OMX bridge online: {self.bridge.url}")
                payload = result.to_mapping()
                payload_data = dict(payload.get("data") or {})
                payload_data["bridge_status"] = bridge_status
                return ActionResult(
                    ok=True,
                    kind="command",
                    name=command.name,
                    message="OMX bridge bringup complete: HTTP/WebSocket bridge online",
                    data=payload_data,
                )
            self.status_store.update(
                "omx",
                online=False,
                connection_status="offline",
                error=str(bridge_status.get("error") or bridge_status),
                message=f"OMX bridge did not become online: {self.bridge.url}",
            )
            return ActionResult(
                ok=False,
                kind="command",
                name=command.name,
                error="omx_bridge_healthcheck_failed",
                message=f"bringup process started, but bridge health check failed: {bridge_status.get('error') or bridge_status}",
                data={"cli": result.to_mapping(), "bridge_status": bridge_status},
            )
        return result

    async def run_task(self, task: TaskDefinition) -> ActionResult:
        if self._teleop_active:
            return ActionResult(ok=False, kind="task", name=task.name, error="teleop_active", message="Cannot start a task while teleop is active.")
        if self._task_lock.locked():
            return ActionResult(
                ok=False,
                kind="task",
                name=task.name,
                error="task_already_running",
                message="Rejected a new task while another task is running.",
                data={"active_task": self._active_task},
            )

        async with self._task_lock:
            self._active_task = task.name
            self.status_store.update("omx", active_action=task.name, message=f"OMX task start: {task.name}")
            try:
                if self._bridge_enabled():
                    result = await asyncio.to_thread(
                        self.bridge.send_sequence,
                        task.name,
                        [self._bridge_step(step) for step in task.steps],
                    )
                    self.status_store.update("omx", message=f"OMX bridge sequence result: {result}")
                    if not self._bridge_ok(result):
                        raise RuntimeError(result.get("error") or result.get("detail") or f"bridge refused sequence: {result}")
                else:
                    for index, step in enumerate(task.steps, start=1):
                        self.status_store.update("omx", message=f"OMX mock step {index}/{len(task.steps)}: {step.type}")
                        await self._execute_step(step)
            except asyncio.CancelledError:
                self.status_store.update("omx", active_action=None, error="cancelled", message="OMX task cancelled")
                raise
            except Exception as exc:
                self.status_store.update("omx", active_action=None, error=str(exc), message=f"OMX task failed: {exc}")
                return ActionResult(ok=False, kind="task", name=task.name, error="task_failed", message=str(exc))
            finally:
                self._active_task = None
                self.status_store.update("omx", active_action=None, message=f"OMX task idle: {task.name}")
        return ActionResult(ok=True, kind="task", name=task.name, message=f"OMX task '{task.display_name}' completed")

    async def start_teleop(self, session_id: str) -> ActionResult:
        if self._task_lock.locked():
            return ActionResult(ok=False, error="task_already_running", message="Cannot start teleop while a task is running.", data={"active_task": self._active_task})
        async with self._teleop_lock:
            if self._teleop_active:
                return ActionResult(ok=True, message="teleop already active", data={"session_id": session_id})
            self._teleop_active = True
            self._latest_teleop_seq = -1
            self.status_store.update("omx", active_action="hand_teleop", message=f"OMX teleop start: {session_id}")
            if self._bridge_enabled():
                result = await asyncio.to_thread(self.bridge.send_enable, True)
                if not self._bridge_ok(result):
                    self._teleop_active = False
                    self.status_store.update("omx", active_action=None, error=str(result), message="OMX bridge teleop enable failed")
                    return ActionResult(ok=False, error="omx_bridge_teleop_enable_failed", message=str(result), data=result)
        return ActionResult(ok=True, message="OMX hand teleop started", data={"session_id": session_id})

    async def handle_teleop_target(self, payload: dict[str, Any]) -> ActionResult:
        if not self._teleop_active:
            return ActionResult(ok=False, error="teleop_not_active", message="No teleop session has been started.")

        seq = int(payload.get("seq", 0))
        now = time.monotonic()
        if seq <= self._latest_teleop_seq:
            return ActionResult(ok=False, error="stale_packet", message="stale teleop packet dropped")
        if now - self._last_teleop_packet_at < 0.02:
            return ActionResult(ok=True, message="debounced teleop target")

        pose = payload.get("pose") or {}
        self._latest_teleop_seq = seq
        self._last_teleop_packet_at = now
        self.status_store.update("omx", message=f"OMX latest target seq={seq} pose={pose}")
        if self._bridge_enabled():
            result = await asyncio.to_thread(self.bridge.send_absolute, {key: float(pose[key]) for key in ("x", "y", "z")})
            if not self._bridge_ok(result):
                self.status_store.update("omx", error=str(result), message="OMX bridge teleop target failed")
                return ActionResult(ok=False, error="omx_bridge_teleop_target_failed", message=str(result), data=result)
        return ActionResult(ok=True, message="teleop target accepted", data={"seq": seq, "latest_target_wins": True})

    async def stop_teleop(self) -> ActionResult:
        async with self._teleop_lock:
            self._teleop_active = False
            self.status_store.update("omx", active_action=None, message="OMX teleop stop")
            if self._bridge_enabled():
                await asyncio.to_thread(self.bridge.send_enable, False)
        return ActionResult(ok=True, message="OMX hand teleop stopped")

    async def stop(self) -> ActionResult:
        self._teleop_active = False
        self._active_task = None
        self.status_store.update("omx", active_action=None, message="OMX Soft Stop")
        cli_result = await self.cli.stop()
        if self._bridge_enabled():
            result = await asyncio.to_thread(self.bridge.send_stop)
            if not self._bridge_ok(result):
                self.status_store.update("omx", error=str(result), message="OMX bridge stop failed")
                return ActionResult(ok=False, error="omx_bridge_stop_failed", message=str(result), data={"bridge": result, "cli": cli_result.to_mapping()})
        return ActionResult(ok=True, message="OMX Soft Stop", data={"cli": cli_result.to_mapping()})

    async def torque_off(self) -> ActionResult:
        """Turn off OMX robot torque."""
        self._teleop_active = False
        self._active_task = None
        self.status_store.update("omx", active_action=None, message="OMX Torque Off")
        if self._bridge_enabled():
            result = await asyncio.to_thread(self.bridge.send_torque_off)
            if self._bridge_ok(result):
                self.status_store.update("omx", online=False, message="OMX torque released")
                return ActionResult(ok=True, message="OMX torque released")
            self.status_store.update("omx", error=str(result), message="OMX bridge torque_off failed")
            return ActionResult(ok=False, error="omx_bridge_torque_off_failed", message=str(result))
        return ActionResult(ok=False, error="omx_bridge_not_available", message="OMX bridge is not connected")

    async def kill_processes(self) -> ActionResult:
        """Force kill OMX robot processes."""
        self._teleop_active = False
        self._active_task = None
        self.status_store.update("omx", active_action=None, message="OMX Process Kill")
        cli_result = await self.cli.stop()
        self.status_store.update("omx", online=False, message="OMX processes killed")
        return ActionResult(ok=True, message="OMX robot processes killed", data={"cli": cli_result.to_mapping()})

    async def handle_task_message(self, payload: dict[str, Any]) -> ActionResult:
        message_type = payload.get("type")
        if message_type == "omx.task.move_l":
            step = TaskStep(
                type="move_l",
                params={
                    **dict(payload.get("pose") or {}),
                    "duration": payload.get("duration", 0.5),
                },
            )
            result = await self._execute_bridge_or_mock_step(step)
            return ActionResult(ok=result["ok"], message=result["message"], error=result.get("error"), data=result.get("data", {}))
        if message_type == "omx.task.gripper":
            step = TaskStep(type="gripper", params={"command": payload.get("command")})
            result = await self._execute_bridge_or_mock_step(step)
            return ActionResult(ok=result["ok"], message=result["message"], error=result.get("error"), data=result.get("data", {}))
        return ActionResult(ok=False, error="unsupported_message", message=f"Unsupported OMX task message: {message_type}")

    async def _execute_bridge_or_mock_step(self, step: TaskStep) -> dict[str, Any]:
        if not self._bridge_enabled():
            await self._execute_step(step)
            return {"ok": True, "message": f"{step.type} accepted in mock mode"}
        if step.type == "move_l":
            pose = {key: float(step.params[key]) for key in ("x", "y", "z")}
            result = await asyncio.to_thread(self.bridge.send_move_l, pose, float(step.params.get("duration", 0.5)))
        elif step.type == "gripper":
            result = await asyncio.to_thread(self.bridge.send_gripper, str(step.params["command"]))
        else:
            return {"ok": False, "error": "unsupported_bridge_step", "message": f"{step.type} is not a bridge primitive"}
        return {
            "ok": self._bridge_ok(result),
            "message": f"bridge {step.type} result: {result}",
            "error": None if self._bridge_ok(result) else "omx_bridge_step_failed",
            "data": result,
        }

    async def _execute_step(self, step: TaskStep) -> None:
        if step.type == "move_l":
            await self._move_l(step.params)
        elif step.type == "gripper":
            await self._gripper(str(step.params["command"]))
        elif step.type == "wait":
            await asyncio.sleep(float(step.params.get("duration", 0.0)))
        elif step.type == "say":
            self.status_store.update("omx", message=f"say: {step.params.get('text')}")
        else:
            raise ValueError(f"unsupported OMX step: {step.type}")

    async def _move_l(self, params: dict[str, Any]) -> None:
        pose = {key: float(params[key]) for key in ("x", "y", "z")}
        duration = float(params.get("duration", 0.5))
        self.status_store.update("omx", message=f"move_l pose={pose} duration={duration} stable={self.stable_preset}")
        await asyncio.sleep(min(duration, 1.0))

    async def _gripper(self, command: str) -> None:
        if command not in {"open", "close"}:
            raise ValueError("gripper command must be open or close")
        now = time.monotonic()
        if now - self._last_button_at < 0.15:
            self.status_store.update("omx", message=f"gripper {command} debounced")
            return
        self._last_button_at = now
        self.status_store.update("omx", message=f"gripper {command}")
        await asyncio.sleep(0.1)

    def _bridge_enabled(self) -> bool:
        return self.mode in {"bridge", "http", "websocket"} and self.bridge.enabled

    def _bridge_ok(self, result: dict[str, Any]) -> bool:
        return bool(result.get("ok", result.get("accepted", False)))

    def _bridge_step(self, step: TaskStep) -> dict[str, Any]:
        if step.type == "move_l":
            return {
                "cmd": "move_l",
                "pose": {key: float(step.params[key]) for key in ("x", "y", "z")},
                "duration": float(step.params.get("duration", 0.5)),
            }
        if step.type == "gripper":
            command = str(step.params["command"])
            return {"cmd": "gripper", "aperture": 1.0 if command == "open" else 0.0}
        if step.type == "wait":
            return {"cmd": "wait", "seconds": float(step.params.get("duration", 0.0))}
        raise ValueError(f"unsupported bridge step: {step.type}")
