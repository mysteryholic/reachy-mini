from __future__ import annotations

from pathlib import Path

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.schemas import TaskDefinition
from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog


# Manual Task Editor builds step-based OMX tasks (move_l / gripper / wait) and
# saves them. We exercise the catalog round-trip on a temp file.
tmp = Path("/tmp/check_manual_task_editor_tasks.yaml")
if tmp.exists():
    tmp.unlink()

catalog = TaskCatalog(paths=[tmp])
task = TaskDefinition.from_mapping(
    {
        "name": "push_box_custom",
        "display_name": "Push Box Custom",
        "device": "omx",
        "triggers": ["push the box", "clear the box"],
        "steps": [
            {"type": "move_l", "params": {"x": 0.2, "y": 0.0, "z": 0.1, "duration": 0.5}},
            {"type": "gripper", "params": {"command": "open"}},
            {"type": "wait", "params": {"duration": 0.3}},
            {"type": "gripper", "params": {"command": "close"}},
        ],
    }
)
catalog.add_or_update(task, persist_path=tmp)

reloaded = TaskCatalog(paths=[tmp])
got = reloaded.get("push_box_custom")
assert got is not None, "saved task not found after reload"
assert [s.type for s in got.steps] == ["move_l", "gripper", "wait", "gripper"], got.steps

export = reloaded.export()
assert "tasks" in export, export

removed = reloaded.delete("push_box_custom", persist=True, persist_path=tmp)
assert removed, "delete failed"
assert TaskCatalog(paths=[tmp]).get("push_box_custom") is None

# The backend remains available, but the builder is not a main-page section.
panel = Path(_bootstrap.ROOT) / "src" / "reachy_robotis" / "robotis_interface" / "web" / "routes.py"
html = panel.read_text(encoding="utf-8")
for marker in ("<h2>5. OMX Manual Task</h2>", "add-movel", "add-open", "add-close", "add-wait", "Save Task"):
    assert marker not in html, marker

tmp.unlink(missing_ok=True)
print("ok manual task editor")
