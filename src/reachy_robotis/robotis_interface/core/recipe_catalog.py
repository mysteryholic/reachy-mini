from __future__ import annotations

from pathlib import Path
from dataclasses import asdict, dataclass, field
from typing import Any

from reachy_robotis.robotis_interface.core.paths import project_path
from reachy_robotis.robotis_interface.core.yaml_loader import dump_mapping, load_mapping


VALID_COMMAND_TYPES = {"host", "container"}
VALID_RUN_MODES = {"foreground", "detached"}


@dataclass(frozen=True)
class RecipeTerminal:
    """One terminal-like command inside a Command Recipe."""

    terminal_id: str
    display_name: str
    connection_id: str
    command_type: str
    command: str
    run_mode: str
    start_order: int
    wait_after_start_sec: float = 0.0
    health_check: str | None = None
    stop_command: str | None = None
    required: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "RecipeTerminal":
        terminal_id = str(data.get("terminal_id") or "").strip()
        connection_id = str(data.get("connection_id") or "").strip()
        command = str(data.get("command") or "").strip()
        command_type = str(data.get("command_type") or "container").strip()
        run_mode = str(data.get("run_mode") or "detached").strip()
        if not terminal_id:
            raise ValueError("recipe terminal requires terminal_id")
        if not connection_id:
            raise ValueError(f"terminal {terminal_id} requires connection_id")
        if not command:
            raise ValueError(f"terminal {terminal_id} requires command")
        if command_type not in VALID_COMMAND_TYPES:
            raise ValueError(f"terminal {terminal_id}: invalid command_type {command_type!r}")
        if run_mode not in VALID_RUN_MODES:
            raise ValueError(f"terminal {terminal_id}: invalid run_mode {run_mode!r}")
        return cls(
            terminal_id=terminal_id,
            display_name=str(data.get("display_name") or terminal_id),
            connection_id=connection_id,
            command_type=command_type,
            command=command,
            run_mode=run_mode,
            start_order=int(data.get("start_order") or 1),
            wait_after_start_sec=float(data.get("wait_after_start_sec") or 0.0),
            health_check=str(data.get("health_check") or "").strip() or None,
            stop_command=str(data.get("stop_command") or "").strip() or None,
            required=bool(data.get("required", True)),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class CommandRecipe:
    """User-facing multi-terminal CLI workflow."""

    recipe_id: str
    display_name: str
    device: str
    description: str
    triggers: list[str] = field(default_factory=list)
    terminals: list[RecipeTerminal] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, recipe_id: str, data: dict[str, Any]) -> "CommandRecipe":
        device = str(data.get("device") or "").strip()
        if not recipe_id:
            raise ValueError("recipe requires an id")
        if not device:
            raise ValueError(f"recipe {recipe_id} requires device")
        terminals = [RecipeTerminal.from_mapping(item) for item in data.get("terminals", [])]
        if not terminals:
            raise ValueError(f"recipe {recipe_id} requires at least one terminal")
        seen = set()
        for terminal in terminals:
            if terminal.terminal_id in seen:
                raise ValueError(f"recipe {recipe_id}: duplicate terminal_id {terminal.terminal_id}")
            seen.add(terminal.terminal_id)
        return cls(
            recipe_id=recipe_id,
            display_name=str(data.get("display_name") or recipe_id),
            device=device,
            description=str(data.get("description") or ""),
            triggers=[str(t).strip() for t in data.get("triggers", []) if str(t).strip()],
            terminals=sorted(terminals, key=lambda item: item.start_order),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "display_name": self.display_name,
            "device": self.device,
            "description": self.description,
            "triggers": list(self.triggers),
            "terminals": [terminal.to_mapping() for terminal in self.terminals],
        }


class RecipeCatalog:
    """Load Command Recipes from config/robotis_recipes.yaml."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or project_path("config", "robotis_recipes.yaml")
        self._recipes: dict[str, CommandRecipe] = {}
        self.reload()

    def reload(self) -> None:
        recipes: dict[str, CommandRecipe] = {}
        if self.path.exists():
            data = load_mapping(self.path)
            raw = data.get("recipes", {})
            if not isinstance(raw, dict):
                raise ValueError("recipes must be a mapping")
            for recipe_id, payload in raw.items():
                recipes[str(recipe_id)] = CommandRecipe.from_mapping(str(recipe_id), dict(payload or {}))
        self._recipes = recipes

    def list_recipes(self) -> list[CommandRecipe]:
        return list(self._recipes.values())

    def get(self, recipe_id: str) -> CommandRecipe | None:
        return self._recipes.get(recipe_id)

    def add_or_update(self, recipe: CommandRecipe, *, persist: bool = False) -> None:
        self._recipes[recipe.recipe_id] = recipe
        if persist:
            self.save()

    def delete(self, recipe_id: str, *, persist: bool = False) -> bool:
        removed = self._recipes.pop(recipe_id, None) is not None
        if removed and persist:
            self.save()
        return removed

    def from_payload(self, recipe_id: str, payload: dict[str, Any]) -> CommandRecipe:
        data = dict(payload)
        data.pop("recipe_id", None)
        return CommandRecipe.from_mapping(recipe_id, data)

    def save(self) -> None:
        dump_mapping(
            self.path,
            {
                "recipes": {
                    recipe.recipe_id: {
                        key: value
                        for key, value in recipe.to_mapping().items()
                        if key != "recipe_id"
                    }
                    for recipe in self.list_recipes()
                }
            },
        )
