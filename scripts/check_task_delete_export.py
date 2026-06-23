from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.schemas import TaskDefinition, TaskStep
from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog


catalog = TaskCatalog()
task = TaskDefinition(
    name="temporary_smoke_task",
    display_name="Temporary Smoke Task",
    triggers=["temporary task"],
    device="omx",
    steps=[TaskStep(type="wait", params={"duration": 0.0})],
)
catalog.add_or_update(task)
assert any(item["name"] == "temporary_smoke_task" for item in catalog.export()["tasks"])  # type: ignore[index]
assert catalog.delete("temporary_smoke_task")
assert catalog.get("temporary_smoke_task") is None
print("ok task delete export")
