from __future__ import annotations

import os
import asyncio

import _bootstrap  # noqa: F401

os.environ["ROBOTIS_CLI_DRY_RUN"] = "1"

from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry
from reachy_robotis.robotis_interface.core.service import get_robotis_executor


registry = DeviceRegistry()

# rosbag play is just a normal allowlisted CLI command (no dedicated subsystem).
for device, bag_path in (
    ("ai_worker", "/workspace/bags/ai_worker_demo_motion"),
    ("omy", "/home/pollen/bags/omy_demo_wave"),
    ("omx", "/workspace/bags/omx_demo_motion"),
):
    spec = registry.command_spec(device, "play_demo_bag")
    assert spec is not None, f"{device} play_demo_bag missing"
    assert spec["command"] == f"ros2 bag play {bag_path}", spec
    assert spec["command_type"] == "container", spec
    assert spec["run_mode"] == "detached", spec


executor = get_robotis_executor()


async def main() -> None:
    # An action triggers the OMX rosbag recipe via the normal conversation path.
    result = await executor.run_action("action", "omx_play_demo_bag")
    assert result.ok, result
    sessions = result.data.get("sessions", [])
    assert sessions, result.data
    command = sessions[0]["command"]
    assert command == "ros2 bag play /workspace/bags/omx_demo_motion", sessions
    assert sessions[0]["run_mode"] == "detached", sessions


asyncio.run(main())
print("ok cli rosbag command")
