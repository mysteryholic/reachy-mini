from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog


with TemporaryDirectory() as tmp:
    path = Path(tmp) / "robotis_recipes.yaml"
    catalog = RecipeCatalog(path)
    recipe = catalog.from_payload(
        "custom_test_recipe",
        {
            "display_name": "Custom Test Recipe",
            "device": "omx",
            "description": "A saved recipe for editor round-trip tests.",
            "triggers": ["start custom test recipe"],
            "terminals": [
                {
                    "terminal_id": "terminal_1",
                    "display_name": "Terminal 1",
                    "connection_id": "omx_pc",
                    "command_type": "container",
                    "command": "ros2 topic list | head -80",
                    "run_mode": "foreground",
                    "start_order": 1,
                    "wait_after_start_sec": 0,
                    "stop_command": "true",
                    "required": True,
                }
            ],
        },
    )
    catalog.add_or_update(recipe, persist=True)
    reloaded = RecipeCatalog(path)
    loaded = reloaded.get("custom_test_recipe")
    assert loaded is not None, path.read_text(encoding="utf-8")
    assert loaded.display_name == "Custom Test Recipe", loaded
    assert loaded.terminals[0].connection_id == "omx_pc", loaded
    assert reloaded.delete("custom_test_recipe", persist=True), "delete failed"
    assert RecipeCatalog(path).get("custom_test_recipe") is None

print("ok recipe save load")
