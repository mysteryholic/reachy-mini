from __future__ import annotations

import asyncio

from reachy_robotis.robotis_interface.adapters.base import RobotAdapter
from reachy_robotis.robotis_interface.core.schemas import ActionResult, CommandDefinition, TaskDefinition
from reachy_robotis.robotis_interface.core.status_store import StatusStore


class MockAdapter(RobotAdapter):
    """Hardware-free demo adapter."""

    def __init__(self, *, status_store: StatusStore, device: str = "mock") -> None:
        super().__init__(device=device, status_store=status_store)
        self._lock = asyncio.Lock()

    async def run_task(self, task: TaskDefinition) -> ActionResult:
        if self._lock.locked():
            return ActionResult(
                ok=False,
                kind="task",
                name=task.name,
                error="task_already_running",
                message="A mock task is already running.",
                data={"active_task": self.status_store.snapshot().get(self.device, {}).get("active_action")},
            )
        async with self._lock:
            self.status_store.update(self.device, active_action=task.name, message=f"mock task start: {task.name}")
            for index, step in enumerate(task.steps, start=1):
                self.status_store.update(self.device, message=f"mock step {index}/{len(task.steps)}: {step.type} {step.params}")
                await asyncio.sleep(min(float(step.params.get("duration", 0.05)), 0.2))
            self.status_store.update(self.device, active_action=None, message=f"mock task done: {task.name}")
        return ActionResult(ok=True, kind="task", name=task.name, message=f"Mock task {task.display_name} completed")

    async def run_command(self, command: CommandDefinition) -> ActionResult:
        self.status_store.update(self.device, active_action=command.name, message=f"mock command: {command.command_key}")
        await asyncio.sleep(0.05)
        self.status_store.update(self.device, active_action=None, message=f"mock command done: {command.name}")
        return ActionResult(ok=True, kind="command", name=command.name, message=f"Mock command {command.display_name} completed")

    async def stop(self) -> ActionResult:
        self.status_store.update(self.device, active_action=None, message="mock soft stop")
        return ActionResult(ok=True, message="Mock Soft Stop")

    async def torque_off(self) -> ActionResult:
        self.status_store.update(self.device, active_action=None, message="mock torque off")
        return ActionResult(ok=True, message="Mock Torque Off")

    async def kill_processes(self) -> ActionResult:
        self.status_store.update(self.device, active_action=None, message="mock kill processes")
        return ActionResult(ok=True, message="Mock Process Kill")
