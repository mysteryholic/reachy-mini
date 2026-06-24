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
    start = await manager.start_recipe("omx_moveit", dry_run=True)
    assert start["ok"], start
    stop = await manager.stop_recipe("omx_moveit", dry_run=True)
    assert stop["ok"], stop
    stopped = [item["session"]["terminal_id"] for item in stop["results"]]
    assert stopped == ["omx_moveit", "omx_bringup"], stopped


asyncio.run(main())
print("ok recipe stop order")
