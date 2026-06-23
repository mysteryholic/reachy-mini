from __future__ import annotations

import asyncio
from typing import Any

from reachy_robotis.tools.core_tools import Tool, ToolDependencies
from reachy_robotis.robotis_interface.core.service import get_robotis_executor


class TestRobotConnection(Tool):
    """Test reachability of a robot connection profile (TCP step)."""

    name = "test_robot_connection"
    description = "Test whether a robot connection profile is reachable over TCP on its SSH port."
    parameters_schema = {
        "type": "object",
        "properties": {
            "connection_id": {
                "type": "string",
                "description": "Connection id such as omy_raspberry_pi, ai_worker_jetson, or omx_pc.",
            },
        },
        "required": ["connection_id"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        cr = get_robotis_executor().connection_registry
        if cr is None:
            return {"ok": False, "error": "connection_registry_unavailable"}
        connection_id = str(kwargs.get("connection_id", ""))
        result = await asyncio.to_thread(cr.test_tcp, connection_id)
        return {"ok": bool(result.get("ok")), **result}
