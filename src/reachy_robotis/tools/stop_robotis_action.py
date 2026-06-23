from __future__ import annotations

from typing import Any

from reachy_robotis.tools.core_tools import Tool, ToolDependencies
from reachy_robotis.robotis_interface.core.service import get_robotis_executor


class StopRobotisAction(Tool):
    """Soft-stop ROBOTIS tasks, teleop, and CLI relays."""

    name = "stop_robotis_action"
    description = "Soft-stop all ROBOTIS actions, or one device when device is provided."
    parameters_schema = {
        "type": "object",
        "properties": {
            "device": {
                "type": "string",
                "description": "Optional device id: omx, omy, ai_worker, mock, or reachy.",
            },
        },
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        device = kwargs.get("device")
        result = await get_robotis_executor().stop(str(device) if device else None)
        return result.to_mapping()

