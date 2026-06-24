from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.command_catalog import CommandCatalog
from reachy_robotis.robotis_interface.core.intent_resolver import IntentResolver
from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog
from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog


actions = ActionCatalog()
recipes = RecipeCatalog()
presets = ProductPresetCatalog()
actions.install_presets(presets.actions())
recipes.install_presets(presets.recipes())
resolver = IntentResolver(TaskCatalog(), CommandCatalog(), actions, recipes)

cases = {
    "start OMX": "omx_bringup",
    "start OMX MoveIt": "omx_moveit",
    "play OMX demo": "omx_demo_bag",
    "start OMY MoveIt": "omy_moveit",
    "start AI Worker": "ai_worker_bg2",
    "start HX5 container": "hx5_container_start",
}
for phrase, action_id in cases.items():
    match = resolver.resolve(phrase)
    assert match.ok and match.name == action_id, (phrase, match)

print("ok conversation uses preset actions")
