from __future__ import annotations

from typing import Any

from reachy_robotis.tools.core_tools import Tool, ToolDependencies
from reachy_robotis.robotis_interface.core.service import get_robotis_executor


class ResolveRobotisIntent(Tool):
    """Resolve a user utterance to a registered ROBOTIS action."""

    name = "resolve_robotis_intent"
    description = "Resolve English user text to one registered ROBOTIS task or command. Does not execute it."
    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "User utterance to resolve, such as 'push the box' or 'start OMY leader mode'.",
            },
        },
        "required": ["text"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        return get_robotis_executor().resolve(str(kwargs.get("text", "")))
