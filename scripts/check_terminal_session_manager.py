from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog
from reachy_robotis.robotis_interface.core.terminal_session_manager import TERMINAL_STATES, TerminalSessionManager


async def main() -> None:
    recipes = RecipeCatalog()
    connections = ConnectionRegistry()
    ProductPresetCatalog().install(connections, recipes, ActionCatalog())
    manager = TerminalSessionManager(recipes, connections)
    assert {"pending", "starting", "running", "exited", "failed", "stopping", "stopped", "unknown"} <= TERMINAL_STATES
    unknown = await manager.start_recipe("does_not_exist", dry_run=True)
    assert not unknown["ok"] and unknown["error"] == "unknown_recipe", unknown
    bad_terminal = await manager.start_terminal("omx_bringup", "does_not_exist", dry_run=True)
    assert not bad_terminal["ok"] and bad_terminal["error"] == "unknown_terminal", bad_terminal
    started = await manager.start_terminal("omx_bringup", "omx_bringup", dry_run=True)
    assert started["ok"], started
    session_id = started["session_id"]
    listed = await manager.list_sessions()
    assert any(session["session_id"] == session_id for session in listed["sessions"]), listed
    logs = await manager.get_session_logs(session_id)
    assert logs["ok"] and logs["session_id"] == session_id, logs
    stopped = await manager.stop_terminal(session_id, dry_run=True)
    assert stopped["ok"] and stopped["session"]["state"] == "stopped", stopped


asyncio.run(main())
print("ok terminal session manager")
