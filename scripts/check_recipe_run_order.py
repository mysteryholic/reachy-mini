from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.core.terminal_session_manager import TerminalSessionManager


async def main() -> None:
    manager = TerminalSessionManager(RecipeCatalog(), ConnectionRegistry())
    result = await manager.start_recipe("omx_moveit", dry_run=True)
    assert result["ok"], result
    terminals = [session["terminal_id"] for session in result["sessions"]]
    assert terminals == ["omx_bringup_f", "omx_moveit"], terminals
    assert all(session["state"] == "running" for session in result["sessions"]), result


asyncio.run(main())
print("ok recipe run order")
