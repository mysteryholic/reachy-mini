from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ActionKind = Literal["task", "command", "recipe", "action"]


@dataclass(frozen=True)
class TaskStep:
    """One serialized robot task step."""

    type: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "TaskStep":
        step_type = str(data.get("type", "")).strip()
        if not step_type:
            raise ValueError("task step requires a type")
        params = data.get("params") or {}
        if not isinstance(params, dict):
            raise ValueError(f"task step {step_type} params must be a mapping")
        return cls(type=step_type, params=dict(params))

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskDefinition:
    """Catalog entry for a registered step-based task."""

    name: str
    display_name: str
    triggers: list[str]
    device: str
    steps: list[TaskStep]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "TaskDefinition":
        name = str(data.get("name", "")).strip()
        device = str(data.get("device", "")).strip()
        if not name:
            raise ValueError("task requires a name")
        if not device:
            raise ValueError(f"task {name} requires a device")
        triggers = [str(item).strip() for item in data.get("triggers", []) if str(item).strip()]
        steps = [TaskStep.from_mapping(item) for item in data.get("steps", [])]
        if not steps:
            raise ValueError(f"task {name} requires at least one step")
        return cls(
            name=name,
            display_name=str(data.get("display_name") or name),
            triggers=triggers,
            device=device,
            steps=steps,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "triggers": list(self.triggers),
            "device": self.device,
            "steps": [step.to_mapping() for step in self.steps],
        }


@dataclass(frozen=True)
class CommandDefinition:
    """Catalog entry for an allowlisted command action."""

    name: str
    display_name: str
    device: str
    type: str
    command_key: str
    triggers: list[str]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "CommandDefinition":
        name = str(data.get("name", "")).strip()
        device = str(data.get("device", "")).strip()
        command_key = str(data.get("command_key", "")).strip()
        if not name:
            raise ValueError("command requires a name")
        if not device:
            raise ValueError(f"command {name} requires a device")
        if not command_key:
            raise ValueError(f"command {name} requires a command_key")
        return cls(
            name=name,
            display_name=str(data.get("display_name") or name),
            device=device,
            type=str(data.get("type") or "cli"),
            command_key=command_key,
            triggers=[str(item).strip() for item in data.get("triggers", []) if str(item).strip()],
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IntentMatch:
    """Result of language-to-action resolution."""

    ok: bool
    kind: ActionKind | None = None
    name: str | None = None
    confidence: float = 0.0
    matched_trigger: str | None = None
    error: str | None = None
    message: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class DeviceStatus:
    """Small status snapshot for UI and tools.

    This is the single source of truth for device state. ``mode``, ``host``,
    ``container`` and ``configured`` are seeded from config at startup;
    ``online``/``connection_status`` only become positive after a real check.
    """

    device: str
    online: bool = False
    mode: str = "mock"
    configured: bool = False
    # not_checked | checking | online | offline | error
    connection_status: str = "not_checked"
    host: str = ""
    container: str = ""
    active_action: str | None = None
    last_message: str = ""
    last_error: str = ""
    log: list[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def append_log(self, message: str, max_lines: int = 50) -> None:
        self.log.append(message)
        self.log = self.log[-max_lines:]
        self.last_message = message
        self.updated_at = time.time()

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActionResult:
    """Execution result returned by adapters and API routes."""

    ok: bool
    kind: ActionKind | None = None
    name: str | None = None
    message: str = ""
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.error is None:
            payload.pop("error", None)
        return payload
