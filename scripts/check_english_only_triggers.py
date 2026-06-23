from __future__ import annotations

import re

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog


hangul = re.compile(r"[\u3131-\u318e\uac00-\ud7a3]")
catalog = ActionCatalog()

for action in catalog.list_actions():
    for trigger in action.triggers:
        assert trigger.strip(), action
        assert not hangul.search(trigger), f"Korean trigger is not allowed: {action.name}: {trigger}"

for recipe in RecipeCatalog().list_recipes():
    for trigger in recipe.triggers:
        assert trigger.strip(), recipe
        assert not hangul.search(trigger), f"Korean trigger is not allowed: {recipe.recipe_id}: {trigger}"

print("ok english only triggers")
