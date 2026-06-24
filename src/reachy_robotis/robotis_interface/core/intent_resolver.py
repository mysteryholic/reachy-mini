from __future__ import annotations

from reachy_robotis.robotis_interface.core.schemas import IntentMatch
from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog
from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.command_catalog import CommandCatalog
from reachy_robotis.robotis_interface.core.trigger_matcher import (
    TriggerCandidate,
    best_trigger_match,
)


class IntentResolver:
    """Resolve user text to a registered action, task, or command."""

    def __init__(
        self,
        task_catalog: TaskCatalog,
        command_catalog: CommandCatalog,
        action_catalog: ActionCatalog | None = None,
        recipe_catalog: RecipeCatalog | None = None,
    ) -> None:
        self.task_catalog = task_catalog
        self.command_catalog = command_catalog
        self.action_catalog = action_catalog
        self.recipe_catalog = recipe_catalog

    def resolve(self, text: str) -> IntentMatch:
        query = text.strip()
        if not query:
            return IntentMatch(ok=False, error="empty_text", message="No input text was provided.")

        match = best_trigger_match(query, self._candidates())
        if match is None:
            return IntentMatch(ok=False, error="no_match", message="No registered action, task, or command matched.")
        return IntentMatch(
            ok=True,
            kind=match.kind,  # type: ignore[arg-type]
            name=match.name,
            confidence=match.score,
            matched_trigger=match.matched_phrase,
        )

    def _candidates(self) -> list[TriggerCandidate]:
        """Resolvable targets in priority order (earlier wins on score ties)."""
        candidates: list[TriggerCandidate] = []
        if self.action_catalog is not None:
            for action in self.action_catalog.list_actions():
                candidates.append(TriggerCandidate("action", action.name, list(action.triggers)))
        for task in self.task_catalog.list_tasks():
            candidates.append(TriggerCandidate("task", task.name, list(task.triggers)))
        for command in self.command_catalog.list_commands():
            candidates.append(TriggerCandidate("command", command.name, list(command.triggers)))
        if self.recipe_catalog is not None:
            for recipe in self.recipe_catalog.list_recipes():
                phrases = [*recipe.triggers, recipe.display_name]
                candidates.append(TriggerCandidate("recipe", recipe.recipe_id, phrases))
        return candidates

