from __future__ import annotations

from typing import Any

from reachy_robotis.tools.core_tools import Tool, ToolDependencies
from reachy_robotis.robotis_interface.core.service import get_robotis_executor


class ListRobotCommands(Tool):
    """List the allowlisted command keys registered for a device."""

    name = "list_robot_commands"
    description = "List the allowlisted command keys for a robot device (e.g. omy, ai_worker, omx)."
    parameters_schema = {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "Device id such as omy, ai_worker, or omx.",
            },
        },
        "required": ["device_id"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        executor = get_robotis_executor()
        reg = executor.registry
        if reg is None:
            return {"ok": False, "error": "device_registry_unavailable"}
        device_id = str(kwargs.get("device_id", ""))
        keys = reg.command_keys(device_id)
        return {
            "ok": True,
            "device": device_id,
            "connection_id": reg.connection_id_for(device_id),
            "commands": [reg.command_spec(device_id, key) for key in keys],
        }
