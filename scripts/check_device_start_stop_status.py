from __future__ import annotations

import os
import asyncio

import _bootstrap  # noqa: F401

os.environ["ROBOTIS_CLI_DRY_RUN"] = "1"  # never execute real SSH in tests

from reachy_robotis.robotis_interface.core.service import get_robotis_executor


executor = get_robotis_executor()


async def main() -> None:
    # Start (bringup) command builds and dry-runs.
    start = await executor.run_device_command("omy", "bringup")
    assert start.ok, start
    assert start.data.get("dry_run") is True, start.data
    assert "omy_ai.launch.py" in start.data.get("built_command", ""), start.data

    # Status command (foreground).
    status = await executor.run_device_command("omy", "status_topics")
    assert status.ok, status
    assert "ros2 topic list" in status.data.get("built_command", ""), status.data

    # Stop command.
    stop = await executor.run_device_command("omy", "stop")
    assert stop.ok, stop
    assert "pkill" in stop.data.get("built_command", ""), stop.data

    # last_command is recorded for /logs.
    last = executor.last_command("omy")
    assert last.get("command_key") == "stop", last
    assert last.get("run_mode") == "foreground", last

    # Unknown command rejected.
    bad = await executor.run_device_command("omy", "halt_and_catch_fire")
    assert not bad.ok and bad.error == "command_not_allowlisted", bad


asyncio.run(main())
print("ok device start stop status")
