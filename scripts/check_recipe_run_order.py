from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog
from reachy_robotis.robotis_interface.core.terminal_session_manager import TerminalSessionManager


async def main() -> None:
    recipes = RecipeCatalog()
    connections = ConnectionRegistry()
    ProductPresetCatalog().install(connections, recipes, ActionCatalog())
    manager = TerminalSessionManager(recipes, connections)
    result = await manager.start_recipe("omx_moveit", dry_run=True)
    assert result["ok"], result
    terminals = [session["terminal_id"] for session in result["sessions"]]
    assert terminals == ["omx_bringup", "omx_moveit"], terminals
    assert all(session["state"] == "running" for session in result["sessions"]), result


asyncio.run(main())
print("ok recipe run order")
