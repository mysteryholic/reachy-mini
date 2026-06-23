from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.service import get_robotis_executor


async def main() -> None:
    executor = get_robotis_executor()
    result = await executor.run_action("task", "mock_full_demo_flow")
    assert result.ok, result
    cli = await executor.run_action("command", "omy_leader_follower")
    assert cli.ok, cli
    print("ok mock actions")


asyncio.run(main())

