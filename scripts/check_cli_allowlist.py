from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.service import get_robotis_executor


async def main() -> None:
    executor = get_robotis_executor()
    ok = await executor.run_action("command", "ai_worker_bringup")
    assert ok.ok, ok
    bad = await executor.run_action("command", "does_not_exist")
    assert not bad.ok and bad.error == "unknown_command", bad
    print("ok cli allowlist")


asyncio.run(main())

