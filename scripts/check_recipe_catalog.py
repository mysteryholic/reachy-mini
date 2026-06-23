from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog


catalog = RecipeCatalog()
recipes = {recipe.recipe_id: recipe for recipe in catalog.list_recipes()}

for recipe_id in (
    "omx_bringup_f",
    "omx_moveit",
    "omx_play_demo_bag",
    "omy_bringup",
    "omy_moveit",
    "omy_play_demo_bag",
    "ai_worker_bringup",
    "ai_worker_demo_command",
):
    assert recipe_id in recipes, (recipe_id, sorted(recipes))
    assert recipes[recipe_id].terminals, recipe_id

print("ok recipe catalog")
