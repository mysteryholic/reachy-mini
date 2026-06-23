from __future__ import annotations

from reachy_robotis.robotis_interface.adapters.base import RobotAdapter
from reachy_robotis.robotis_interface.core.schemas import ActionResult
from reachy_robotis.robotis_interface.core.status_store import StatusStore


class ReachyAdapter(RobotAdapter):
    """Adapter placeholder for Reachy Mini speech/status coordination."""

    def __init__(self, *, status_store: StatusStore) -> None:
        super().__init__(device="reachy", status_store=status_store)
        self.status_store.update("reachy", mode="conversation", online=True, message="Reachy Mini conversation hub ready")

    async def stop(self) -> ActionResult:
        self.status_store.update("reachy", active_action=None, message="reachy soft stop")
        return ActionResult(ok=True, message="Reachy Soft Stop")

    async def torque_off(self) -> ActionResult:
        self.status_store.update("reachy", active_action=None, message="reachy torque off")
        return ActionResult(ok=True, message="Reachy Torque Off")

    async def kill_processes(self) -> ActionResult:
        self.status_store.update("reachy", active_action=None, message="reachy kill processes")
        return ActionResult(ok=True, message="Reachy Process Kill")
