from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog


catalog = TaskCatalog()
tasks = catalog.list_tasks()
assert catalog.get("push_box_custom") is not None
assert len(tasks) >= 2
print(f"ok task catalog: {len(tasks)} task(s)")

