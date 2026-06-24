from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog


actions = {action.name: action for action in ProductPresetCatalog().actions()}

for action_id in ("omx_bringup", "omx_moveit", "omy_moveit", "ai_worker_bg2", "hx5_container_start"):
    action = actions[action_id]
    assert action.kind == "recipe"
    assert action.run == {"method": "start_recipe", "recipe_id": action_id}
    assert action.triggers

all_actions = ActionCatalog()
all_recipes = RecipeCatalog()
all_actions.install_presets(ProductPresetCatalog().actions())
all_recipes.install_presets(ProductPresetCatalog().recipes())
for action in all_actions.list_actions():
    if action.run.get("method") == "start_recipe":
        recipe_id = str(action.run.get("recipe_id") or action.name)
        assert all_recipes.get(recipe_id) is not None, (action.name, recipe_id)

print("ok preset actions")
