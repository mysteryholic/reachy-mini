from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog


catalog = RecipeCatalog()
catalog.install_presets(ProductPresetCatalog().recipes())
recipes = {recipe.recipe_id: recipe for recipe in catalog.list_recipes()}

for recipe_id in (
    "omx_bringup",
    "omx_moveit",
    "omx_demo_bag",
    "omy_teleop",
    "omy_moveit",
    "omy_demo_bag",
    "ai_worker_bg2",
    "hx5_container_start",
):
    assert recipe_id in recipes, (recipe_id, sorted(recipes))
    assert recipes[recipe_id].terminals, recipe_id

print("ok recipe catalog")
