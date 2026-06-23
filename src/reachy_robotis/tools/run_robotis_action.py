from __future__ import annotations

from typing import Any

from reachy_robotis.tools.core_tools import Tool, ToolDependencies
from reachy_robotis.robotis_interface.core.service import get_robotis_executor


class RunRobotisAction(Tool):
    """Run a registered ROBOTIS action by name."""

    name = "run_robotis_action"
    description = "Run a registered ROBOTIS action, saved recipe, task, or command by catalog name. Also accepts a user phrase to resolve a trigger. Never accepts shell commands."
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
            # Exact registered action name -> run it directly.
            result = await executor.run_action("action", name)
        elif executor.recipe_catalog is not None and executor.recipe_catalog.get(name) is not None:
            # Exact saved recipe id (e.g. resolved kind="recipe") -> run the recipe.
            result = await executor.run_action("recipe", name)
        else:
            # Otherwise treat the input as user text and resolve a trigger.
            result = await executor.run_resolved_text(name)
        return result.to_mapping()

