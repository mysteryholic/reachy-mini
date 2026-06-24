from __future__ import annotations

from typing import Any

from reachy_robotis.tools.core_tools import Tool, ToolDependencies
from reachy_robotis.robotis_interface.core.service import get_robotis_executor


class RunRobotisAction(Tool):
    """Run a registered ROBOTIS action by name."""

    name = "run_robotis_action"
    description = (
        "Run an OMX/OMY/AI Worker action on the robot. Use this whenever the user asks to "
        "do something that matches a saved trigger phrase (e.g. 'start OMX MoveIt', "
        "'bring up OMX', 'play the OMX demo', 'start OMY MoveIt'). Pass the user's exact "
        "utterance as 'name' and the best-matching trigger is resolved and executed in one "
        "step; a friendly 'reply' plus the matched trigger comes back. Never accepts shell commands."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Registered action/recipe name (preferred), or a user phrase to resolve when kind is omitted.",
            },
            "kind": {
                "type": "string",
                "enum": ["action", "recipe", "task", "command"],
                "description": "Optional kind. If omitted, name is matched against registered action names, then saved recipe ids, then resolved as user text.",
            },
        },
        "required": ["name"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        executor = get_robotis_executor()
        name = str(kwargs.get("name", ""))
        kind = kwargs.get("kind")
        if kind:
            result = await executor.run_action(str(kind), name)
        elif executor.action_catalog is not None and executor.action_catalog.get(name) is not None:
            result = await executor.run_action("action", name)
        elif executor.recipe_catalog is not None and executor.recipe_catalog.get(name) is not None:
            result = await executor.run_action("recipe", name)
        else:
            result = await executor.run_resolved_text(name)
        return result.to_mapping()

