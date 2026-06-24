from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog


recipe = next(recipe for recipe in ProductPresetCatalog().recipes() if recipe.recipe_id == "omy_moveit")
assert recipe is not None, "omy_moveit recipe missing"
assert recipe.device == "omy", recipe
assert len(recipe.terminals) >= 2, recipe
commands = [terminal.command for terminal in recipe.terminals]
assert "ros2 launch open_manipulator_bringup omy_f3m.launch.py" in commands, commands
assert "ros2 launch open_manipulator_moveit_config omy_f3m_moveit.launch.py" in commands, commands
assert [terminal.start_order for terminal in recipe.terminals] == [1, 2], recipe.terminals

print("ok omy moveit recipe")
