from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.schemas import TaskDefinition, TaskStep
from reachy_robotis.robotis_interface.core.status_store import StatusStore
from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry
from reachy_robotis.robotis_interface.adapters.omx_adapter import OMXAdapter


# Force mock mode so the guard is validated deterministically, independent of
# whether the real OMX bridge is reachable. (With a live-but-closed bridge the
# first task fails fast on connection-refused and the timing race disappears.)
registry = DeviceRegistry()
omx_config = registry.get("omx")
omx_config["mode"] = "mock"
registry._devices["omx"] = omx_config  # noqa: SLF001

adapter = OMXAdapter(status_store=StatusStore(), registry=registry)
task = TaskDefinition(
    name="push_box_custom",
    display_name="Push Box",
    triggers=[],
    device="omx",
    steps=[TaskStep(type="wait", params={"duration": 0.2})],
)


async def main() -> None:
    first = asyncio.create_task(adapter.run_task(task))
    await asyncio.sleep(0.02)
    second = await adapter.run_task(task)
    await first
    assert not second.ok, second
    assert second.error == "task_already_running", second
    print("ok duplicate guard")


asyncio.run(main())

