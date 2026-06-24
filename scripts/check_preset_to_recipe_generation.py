from __future__ import annotations

import _bootstrap  # noqa: F401

from pathlib import Path
from tempfile import TemporaryDirectory

from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog


recipes = {recipe.recipe_id: recipe for recipe in ProductPresetCatalog().recipes()}

assert len(recipes["omx_moveit"].terminals) == 2
assert len(recipes["omy_moveit"].terminals) == 2
assert recipes["omx_moveit"].terminals[1].command.endswith("omx_f_moveit.launch.py")
assert recipes["omy_moveit"].terminals[1].command.endswith("omy_f3m_moveit.launch.py")
assert recipes["ai_worker_bg2"].terminals[0].command == "ros2 launch ffw_bringup ffw_bg2_ai.launch.py"
assert recipes["hx5_container_start"].terminals[0].command == "./docker/container.sh start"
assert recipes["hx5_container_start"].terminals[0].command_type == "host"

with TemporaryDirectory() as directory:
    root = Path(directory)
    connections = ConnectionRegistry(root / "connections.yaml")
    generated_recipes = RecipeCatalog(root / "recipes.yaml")
    generated_actions = ActionCatalog(root / "actions.yaml")
    ProductPresetCatalog().install(connections, generated_recipes, generated_actions)
    assert connections.get("omx_pc") is not None
    assert connections.get("omy_raspberry_pi") is not None
    assert connections.get("ai_worker_jetson") is not None
    assert connections.get("hx5_hand") is not None
    assert generated_recipes.get("omy_moveit") is not None
    assert generated_actions.get("hx5_container_start") is not None

print("ok preset to recipe generation")
