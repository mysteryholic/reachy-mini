from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.status_store import StatusStore
from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry
from reachy_robotis.robotis_interface.transports.cli_transport import CLITransport
from reachy_robotis.robotis_interface.core.schemas import CommandDefinition


registry = DeviceRegistry()
status = StatusStore()

omx_preview = CLITransport("omx", registry, status).preview_command("bringup_f")
assert omx_preview["ok"], omx_preview
omx_args = " ".join(omx_preview["args"])  # type: ignore[index]
assert "ssh" in omx_args and "robotis@192.168.60.74" in omx_args, omx_args
assert "docker exec" in omx_args and "open_manipulator" in omx_args, omx_args
assert "cd /root/ros2_ws" in omx_args, omx_args
assert "source /opt/ros/jazzy/setup.bash" in omx_args, omx_args
assert "source /root/ros2_ws/install/setup.bash" in omx_args, omx_args
assert "ros2 launch open_manipulator_bringup omx_f.launch.py" in omx_args, omx_args

omy_preview = CLITransport("omy", registry, status).preview_command("leader_follower")
assert omy_preview["ok"], omy_preview
omy_args = " ".join(omy_preview["args"])  # type: ignore[index]
assert "ssh" in omy_args and "docker exec" in omy_args and "omy_ros2" in omy_args and "source /opt/ros/humble/setup.bash" in omy_args, omy_args

ai_preview = CLITransport("ai_worker", registry, status).preview_command("bringup")
assert ai_preview["ok"], ai_preview
ai_args = " ".join(ai_preview["args"])  # type: ignore[index]
assert "ssh" in ai_args and "docker exec" in ai_args and "ai_worker_ros2" in ai_args and "ffw_bringup" in ai_args, ai_args


async def check_config_error() -> None:
    broken = DeviceRegistry()
    broken._devices["broken"] = {  # noqa: SLF001
        "mode": "ssh_docker",
        "host": "127.0.0.1",
        "dry_run": True,
        "commands": {"bringup": "ros2 launch demo demo.launch.py"},
    }
    transport = CLITransport("broken", broken, StatusStore())
    result = await transport.run(
        CommandDefinition(
            name="broken_bringup",
            display_name="Broken Bringup",
            device="broken",
            type="cli",
            command_key="bringup",
            triggers=[],
        )
    )
    assert not result.ok, result
    assert result.error == "cli_config_error", result


asyncio.run(check_config_error())
print("ok ssh docker paths")
