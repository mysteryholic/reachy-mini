from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog


recipe = RecipeCatalog().get("omx_moveit")
assert recipe is not None, "omx_moveit recipe missing"
assert recipe.device == "omx", recipe
assert len(recipe.terminals) >= 2, recipe
commands = [terminal.command for terminal in recipe.terminals]
assert "ros2 launch open_manipulator_bringup omx_f.launch.py" in commands, commands
assert "ros2 launch open_manipulator_moveit_config omx_f_moveit.launch.py" in commands, commands
assert [terminal.start_order for terminal in recipe.terminals] == [1, 2], recipe.terminals

print("ok omx moveit recipe")
