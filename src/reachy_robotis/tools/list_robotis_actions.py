from __future__ import annotations

from typing import Any

from reachy_robotis.tools.core_tools import Tool, ToolDependencies
from reachy_robotis.robotis_interface.core.service import get_robotis_executor


class ListRobotisActions(Tool):
    """List registered ROBOTIS tasks and commands."""

    name = "list_robotis_actions"
    description = "List the registered ROBOTIS task and command names that can be run safely."
    parameters_schema = {"type": "object", "properties": {}, "required": []}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        return {"ok": True, **get_robotis_executor().list_actions()}

