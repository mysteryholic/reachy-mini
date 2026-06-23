from __future__ import annotations

from pathlib import Path

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog
from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog, ActionDefinition
from reachy_robotis.robotis_interface.core.command_catalog import CommandCatalog
from reachy_robotis.robotis_interface.core.intent_resolver import IntentResolver


# Adding a new action makes it resolvable without touching code.
tmp = Path("/tmp/check_action_catalog_extension.yaml")
tmp.write_text('{"actions": []}\n', encoding="utf-8")
catalog = ActionCatalog(path=tmp)

catalog.add_or_update(
    ActionDefinition.from_mapping(
        {
            "name": "omy_custom_demo",
            "display_name": "OMY Custom Demo",
            "kind": "cli_command",
            "device": "omy",
            "triggers": ["OMY custom demo", "run OMY custom demo"],
            "run": {"method": "run_command", "command_key": "play_demo_bag"},
        }
    )
)
catalog.save()

reloaded = ActionCatalog(path=tmp)
assert reloaded.get("omy_custom_demo") is not None, "new action not persisted"

resolver = IntentResolver(TaskCatalog(), CommandCatalog(), reloaded)
match = resolver.resolve("run omy custom demo")
assert match.ok and match.kind == "action" and match.name == "omy_custom_demo", match

# Invalid kind rejected at load time.
try:
    ActionDefinition.from_mapping({"name": "bad", "kind": "free_shell", "device": "omy"})
    raise SystemExit("invalid kind should have raised")
except ValueError:
    pass

tmp.unlink(missing_ok=True)
print("ok action catalog extension")
