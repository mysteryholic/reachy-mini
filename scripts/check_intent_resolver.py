from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog
from reachy_robotis.robotis_interface.core.command_catalog import CommandCatalog
from reachy_robotis.robotis_interface.core.intent_resolver import IntentResolver


resolver = IntentResolver(TaskCatalog(), CommandCatalog())
cases = {
    "start OMY leader mode": ("command", "omy_leader_follower"),
    "start AI Worker": ("command", "ai_worker_bringup"),
    "push the box": ("task", "push_box_custom"),
}
for text, expected in cases.items():
    match = resolver.resolve(text)
    assert match.ok, match
    assert (match.kind, match.name) == expected, match
assert not resolver.resolve("make coffee").ok
print("ok intent resolver")
