from __future__ import annotations

from pathlib import Path
from dataclasses import field, dataclass
from typing import Any

from reachy_robotis.robotis_interface.core.paths import project_path
from reachy_robotis.robotis_interface.core.yaml_loader import load_mapping


# Action kinds the catalog understands. They all resolve to an allowlisted
# operation; an LLM only ever selects an action name, never a shell command.
VALID_KINDS = {"recipe", "cli_command", "stop", "manual_task", "teleop_mode", "status", "mode"}


@dataclass(frozen=True)
class ActionDefinition:
    """One registered action that voice/chat/UI can select by name."""

    name: str
    display_name: str
    kind: str
    device: str
    triggers: list[str]
    run: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ActionDefinition":
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError("action requires a name")
        kind = str(data.get("kind", "")).strip()
        if kind not in VALID_KINDS:
            raise ValueError(f"action {name}: invalid kind {kind!r}")
        device = str(data.get("device", "")).strip()
        if not device:
            raise ValueError(f"action {name} requires a device")
        run = data.get("run") or {}
        if not isinstance(run, dict):
            raise ValueError(f"action {name}: run must be a mapping")
        return cls(
            name=name,
            display_name=str(data.get("display_name") or name),
            kind=kind,
            device=device,
            triggers=[str(t).strip() for t in (data.get("triggers") or []) if str(t).strip()],
            run=dict(run),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "kind": self.kind,
            "device": self.device,
            "triggers": list(self.triggers),
            "run": dict(self.run),
        }


class ActionCatalog:
    """Load and serve registered actions from robotis_actions.yaml."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or project_path("config", "robotis_actions.yaml")
        self._actions: dict[str, ActionDefinition] = {}
        self.reload()

    def reload(self) -> None:
        actions: dict[str, ActionDefinition] = {}
        if self.path.exists():
            data = load_mapping(self.path)
            for item in data.get("actions", []):
                action = ActionDefinition.from_mapping(item)
                actions[action.name] = action
        self._actions = actions

    def list_actions(self) -> list[ActionDefinition]:
        return list(self._actions.values())

    def get(self, name: str) -> ActionDefinition | None:
        return self._actions.get(name)

    def add_or_update(self, action: ActionDefinition) -> None:
        self._actions[action.name] = action

    def install_presets(self, actions: list[ActionDefinition]) -> None:
        """Put generated product actions first so preset triggers win ties."""
        preset_names = {action.name for action in actions}
        remaining = {name: action for name, action in self._actions.items() if name not in preset_names}
        self._actions = {action.name: action for action in actions}
        self._actions.update(remaining)

    def save(self) -> None:
        from reachy_robotis.robotis_interface.core.yaml_loader import dump_mapping

        dump_mapping(self.path, {"actions": [a.to_mapping() for a in self._actions.values()]})
