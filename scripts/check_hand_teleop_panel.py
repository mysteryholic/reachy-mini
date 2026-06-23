from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.status_store import StatusStore
from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry
from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.adapters.omx_adapter import OMXAdapter


# Hand teleop is a registered teleop_mode action.
actions = ActionCatalog()
teleop = actions.get("omx_hand_teleop")
assert teleop is not None and teleop.kind == "teleop_mode", teleop
assert teleop.run.get("method") == "start_hand_teleop", teleop.run

# OMX adapter exposes teleop lifecycle in mock mode (no bridge needed).
registry = DeviceRegistry()
cfg = registry.get("omx")
cfg["mode"] = "mock"
registry._devices["omx"] = cfg  # noqa: SLF001
adapter = OMXAdapter(status_store=StatusStore(), registry=registry)


async def main() -> None:
    started = await adapter.start_teleop("test-session")
    assert started.ok, started

    # latest-target-wins / stale packet drop.
    first = await adapter.handle_teleop_target({"seq": 5, "pose": {"x": 0.1, "y": 0.0, "z": 0.1}})
    assert first.ok, first
    stale = await adapter.handle_teleop_target({"seq": 1, "pose": {"x": 0.0, "y": 0.0, "z": 0.0}})
    assert not stale.ok and stale.error == "stale_packet", stale

    # task running rejects teleop start.
    adapter._teleop_active = False  # noqa: SLF001
    import reachy_robotis.robotis_interface.core.schemas as s

    task = s.TaskDefinition(name="t", display_name="t", triggers=[], device="omx", steps=[s.TaskStep(type="wait", params={"duration": 0.3})])
    running = asyncio.create_task(adapter.run_task(task))
    await asyncio.sleep(0.02)
    rejected = await adapter.start_teleop("x")
    assert not rejected.ok and rejected.error == "task_already_running", rejected
    await running

    stopped = await adapter.stop_teleop()
    assert stopped.ok, stopped


asyncio.run(main())
print("ok hand teleop panel")
