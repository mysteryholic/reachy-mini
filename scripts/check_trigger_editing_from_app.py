from pathlib import Path
from tempfile import TemporaryDirectory
import shutil

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.command_catalog import CommandCatalog
from reachy_robotis.robotis_interface.core.intent_resolver import IntentResolver
from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog
from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog


ROOT = Path(__file__).resolve().parents[1]
routes = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()
javascript = (ROOT / "src/reachy_robotis/robotis_interface/web/static/robotis_panel.js").read_text()
presets = (ROOT / "src/reachy_robotis/robotis_interface/core/product_presets.py").read_text()

assert "Talk to Reachy" not in routes
assert "Conversation triggers" in javascript
assert "data-advanced-triggers" in javascript
assert "one trigger phrase per line" in javascript
assert "JSON.stringify({ triggers, terminals })" in javascript
assert 'triggers = payload.get("triggers")' in presets
assert "requires at least one trigger" in presets
assert '@router.put("/products/{product_id}/workflows/{workflow_id}")' in routes

with TemporaryDirectory() as directory:
    path = Path(directory) / "presets.yaml"
    shutil.copyfile(ROOT / "config/robotis_product_presets.yaml", path)
    catalog = ProductPresetCatalog(path)
    recipe = next(item for item in catalog.recipes() if item.recipe_id == "omx_moveit")
    catalog.update_workflow(
        "omx",
        "omx_moveit",
        {
            "triggers": ["activate my OMX planner"],
            "terminals": [terminal.to_mapping() for terminal in recipe.terminals],
        },
    )
    recipes = RecipeCatalog(Path(directory) / "recipes.yaml")
    actions = ActionCatalog(Path(directory) / "actions.yaml")
    recipes.install_presets(catalog.recipes())
    actions.install_presets(catalog.actions())
    match = IntentResolver(TaskCatalog(paths=[]), CommandCatalog(), actions, recipes).resolve(
        "activate my OMX planner"
    )
    assert match.ok and match.name == "omx_moveit", match

print("ok trigger editing from app")
