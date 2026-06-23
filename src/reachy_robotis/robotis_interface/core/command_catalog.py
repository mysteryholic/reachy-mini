from __future__ import annotations

from pathlib import Path

from reachy_robotis.robotis_interface.core.paths import project_path
from reachy_robotis.robotis_interface.core.schemas import CommandDefinition
from reachy_robotis.robotis_interface.core.yaml_loader import load_mapping


class CommandCatalog:
    """Load and list registered command actions."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or project_path("config", "robotis_commands.yaml")
        self._commands: dict[str, CommandDefinition] = {}
        self.reload()

    def reload(self) -> None:
        commands: dict[str, CommandDefinition] = {}
        if self.path.exists():
            data = load_mapping(self.path)
            for item in data.get("commands", []):
                command = CommandDefinition.from_mapping(item)
                commands[command.name] = command
        self._commands = commands

    def list_commands(self) -> list[CommandDefinition]:
        return list(self._commands.values())

    def get(self, name: str) -> CommandDefinition | None:
        return self._commands.get(name)

