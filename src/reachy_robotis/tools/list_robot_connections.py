from __future__ import annotations

from typing import Any

from reachy_robotis.tools.core_tools import Tool, ToolDependencies
from reachy_robotis.robotis_interface.core.service import get_robotis_executor


class ListRobotConnections(Tool):
    """List configured robot SSH connection profiles (no secrets)."""

    name = "list_robot_connections"
    description = "List the configured robot connection profiles (id, host, transport). Never returns secrets."
    parameters_schema = {"type": "object", "properties": {}, "required": []}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        cr = get_robotis_executor().connection_registry
        if cr is None:
            return {"ok": False, "error": "connection_registry_unavailable", "connections": []}
        return {
            "ok": True,
            "connections": [
                {
                    "connection_id": p.connection_id,
                    "display_name": p.display_name,
                    "host": p.host,
                    "transport": p.transport,
                    "container_name": p.container_name,
                }
                for p in cr.list_connections().values()
            ],
        }
