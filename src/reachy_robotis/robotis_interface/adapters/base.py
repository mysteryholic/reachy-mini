from __future__ import annotations

import abc

from reachy_robotis.robotis_interface.core.schemas import ActionResult, CommandDefinition, TaskDefinition
from reachy_robotis.robotis_interface.core.status_store import StatusStore


class RobotAdapter(abc.ABC):
    """Base interface for task and command execution backends."""

    device: str

    def __init__(self, *, device: str, status_store: StatusStore) -> None:
        self.device = device
        self.status_store = status_store
        self.status_store.ensure_device(device)

    async def run_task(self, task: TaskDefinition) -> ActionResult:
        return ActionResult(ok=False, kind="task", name=task.name, error="unsupported_task", message=f"{self.device} does not support task execution.")

    async def run_command(self, command: CommandDefinition) -> ActionResult:
        return ActionResult(
            ok=False,
            kind="command",
            name=command.name,
            error="unsupported_command",
            message=f"{self.device} does not support command execution.",
        )

    @abc.abstractmethod
    async def stop(self) -> ActionResult:
        """Soft-stop current work."""

    async def torque_off(self) -> ActionResult:
        """Turn off robot torque/power."""
        return ActionResult(
            ok=False,
            error="unsupported_torque_off",
            message=f"{self.device} does not support torque_off."
        )

    async def kill_processes(self) -> ActionResult:
        """Force kill all robot processes."""
        return ActionResult(
            ok=False,
            error="unsupported_kill",
            message=f"{self.device} does not support process kill."
        )

    async def cancel_active_action(self) -> ActionResult:
        """Cancel currently running action."""
        return ActionResult(
            ok=True,
            message=f"Cancelled the active action on {self.device}."
        )

    async def probe(self) -> dict:
        """Refresh live connectivity for this device.

        Default is a no-op that reports the currently stored snapshot. Remote
        adapters override this to run a real check (SSH/Docker, HTTP bridge).
        """
        return {"ok": True, "device": self.device, "checked": False}

