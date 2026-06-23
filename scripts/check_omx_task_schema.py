from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.schemas import TaskStep
from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog


catalog = TaskCatalog()
catalog.validate_step(TaskStep(type="move_l", params={"x": 0.18, "y": 0.1, "z": 0.18, "duration": 0.5}))
catalog.validate_step(TaskStep(type="gripper", params={"command": "open"}))
catalog.validate_step(TaskStep(type="wait", params={"duration": 0.1}))
try:
    catalog.validate_step(TaskStep(type="gripper", params={"command": "explode"}))
except ValueError:
    print("ok omx task schema")
else:
    raise AssertionError("invalid gripper command accepted")

