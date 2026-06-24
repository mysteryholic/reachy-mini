from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog
from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.terminal_session_manager import TerminalSessionManager


ROOT = Path(__file__).resolve().parents[1]
javascript = (ROOT / "src/reachy_robotis/robotis_interface/web/static/robotis_panel.js").read_text()
routes = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()

for label in (
    "New Custom Workflow",
    "Reuse terminal",
    "Add Existing Terminal",
    "Add Custom Terminal",
    "Workflow ID",
    "Start order",
    "Wait after start",
):
    assert label in javascript, label

for hook in (
    "startNewWorkflow",
    "addExistingTerminal",
    "addCustomTerminal",
    'method: creating ? "POST" : "PUT"',
):
    assert hook in javascript, hook

assert '@router.post("/products/{product_id}/workflows/{workflow_id}")' in routes

with TemporaryDirectory() as directory:
    root = Path(directory)
    preset_path = root / "presets.yaml"
    shutil.copyfile(ROOT / "config/robotis_product_presets.yaml", preset_path)
    presets = ProductPresetCatalog(preset_path)
    omx_moveit = next(recipe for recipe in presets.recipes() if recipe.recipe_id == "omx_moveit")
    reused = omx_moveit.terminals[0].to_mapping()
    reused["terminal_id"] = "reused_bringup"
    reused["start_order"] = 1
    custom = {
        "terminal_id": "custom_status",
        "display_name": "Custom Status",
        "command_type": "container",
        "command": "ros2 topic list",
        "run_mode": "foreground",
        "start_order": 2,
        "wait_after_start_sec": 0,
        "stop_command": "true",
        "required": True,
    }
    presets.create_workflow(
        "omx",
        "omx_custom_check",
        {
            "display_name": "OMX Custom Check",
            "description": "Reuse bringup, then list topics.",
            "triggers": ["run OMX custom check"],
            "terminals": [reused, custom],
        },
    )
    recipes = RecipeCatalog(root / "recipes.yaml")
    connections = ConnectionRegistry(root / "connections.yaml")
    actions = ActionCatalog(root / "actions.yaml")
    connection_id, connection = presets.connection_payload(
        "omx",
        host="192.0.2.20",
        user="robotis",
        auth={"method": "ssh_key", "key_path": "~/.ssh/id_ed25519"},
    )
    connections.save_connection(connection_id, connection)
    presets.install(connections, recipes, actions)
    recipe = recipes.get("omx_custom_check")
    assert recipe is not None
    assert [terminal.terminal_id for terminal in recipe.terminals] == ["reused_bringup", "custom_status"]
    assert actions.get("omx_custom_check") is not None

    async def run() -> None:
        result = await TerminalSessionManager(recipes, connections).start_recipe(
            "omx_custom_check",
            dry_run=True,
        )
        assert result["ok"], result
        assert [session["terminal_id"] for session in result["sessions"]] == [
            "reused_bringup",
            "custom_status",
        ]

    asyncio.run(run())

print("ok custom workflow composer")
