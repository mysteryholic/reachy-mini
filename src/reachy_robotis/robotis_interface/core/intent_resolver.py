from __future__ import annotations

import re
from difflib import SequenceMatcher

from reachy_robotis.robotis_interface.core.schemas import IntentMatch
from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog
from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.command_catalog import CommandCatalog


def normalize_text(text: str) -> str:
    """Normalize trigger text for deterministic matching."""
    return re.sub(r"\s+", " ", text.strip().casefold())


class IntentResolver:
    """Resolve user text to a registered action, task, or command.

    ``action_catalog`` (robotis_actions.yaml) is the preferred source and is
    checked first; task/command catalogs remain for backward compatibility.
    """

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

        exact = self._match_exact(query)
        if exact:
            return exact

        normalized = self._match_normalized(query)
        if normalized:
            return normalized

        fuzzy = self._match_fuzzy(query)
        if fuzzy:
            return fuzzy

        return IntentMatch(ok=False, error="no_match", message="No registered action, task, or command matched.")

    def _iter_actions(self) -> list[tuple[str, str, list[str]]]:
        actions: list[tuple[str, str, list[str]]] = []
        # Action catalog first so registered actions win on equal matches.
        if self.action_catalog is not None:
            actions.extend(("action", action.name, action.triggers) for action in self.action_catalog.list_actions())
        actions.extend(("task", task.name, task.triggers) for task in self.task_catalog.list_tasks())
        actions.extend(("command", command.name, command.triggers) for command in self.command_catalog.list_commands())
        # Recipe triggers last so a registered action (with explicit run.method)
        # still wins, but recipes saved only in Command Recipe (no matching
        # action) are still reachable by their trigger sentence. kind="recipe"
        # is dispatched by ActionExecutor.run_action -> start_recipe(recipe_id).
        if self.recipe_catalog is not None:
            actions.extend(
                ("recipe", recipe.recipe_id, recipe.triggers) for recipe in self.recipe_catalog.list_recipes()
            )
        return actions

    def _match_exact(self, query: str) -> IntentMatch | None:
        for kind, name, triggers in self._iter_actions():
            for trigger in triggers:
                if query == trigger:
                    return IntentMatch(ok=True, kind=kind, name=name, confidence=0.95, matched_trigger=trigger)  # type: ignore[arg-type]
        return None

    def _match_normalized(self, query: str) -> IntentMatch | None:
        normalized_query = normalize_text(query)
        for kind, name, triggers in self._iter_actions():
            for trigger in triggers:
                if normalized_query == normalize_text(trigger):
                    return IntentMatch(ok=True, kind=kind, name=name, confidence=0.9, matched_trigger=trigger)  # type: ignore[arg-type]
        return None

    def _match_fuzzy(self, query: str) -> IntentMatch | None:
        normalized_query = normalize_text(query)
        best: IntentMatch | None = None
        best_score = 0.0
        for kind, name, triggers in self._iter_actions():
            for trigger in triggers:
                normalized_trigger = normalize_text(trigger)
                if normalized_trigger in normalized_query or normalized_query in normalized_trigger:
                    score = 0.82
                else:
                    score = SequenceMatcher(None, normalized_query, normalized_trigger).ratio()
                if score > best_score:
                    best_score = score
                    best = IntentMatch(
                        ok=True,
                        kind=kind,  # type: ignore[arg-type]
                        name=name,
                        confidence=round(score, 3),
                        matched_trigger=trigger,
                    )
        if best is not None and best_score >= 0.68:
            return best
        return None

