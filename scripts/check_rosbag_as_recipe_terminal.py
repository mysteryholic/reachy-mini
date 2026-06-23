from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog


catalog = RecipeCatalog()
for recipe_id, command in (
    ("omx_play_demo_bag", "ros2 bag play /workspace/bags/omx_demo_motion"),
    ("omy_play_demo_bag", "ros2 bag play /home/pollen/bags/omy_demo_wave"),
    ("ai_worker_demo_command", "ros2 bag play /workspace/bags/ai_worker_demo_motion"),
):
    recipe = catalog.get(recipe_id)
    assert recipe is not None, recipe_id
    assert any(terminal.command == command for terminal in recipe.terminals), recipe.to_mapping()

print("ok rosbag as recipe terminal")
