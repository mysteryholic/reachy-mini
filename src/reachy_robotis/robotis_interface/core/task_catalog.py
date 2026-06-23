from __future__ import annotations

from pathlib import Path

from reachy_robotis.robotis_interface.core.paths import project_path
from reachy_robotis.robotis_interface.core.schemas import TaskDefinition, TaskStep
from reachy_robotis.robotis_interface.core.yaml_loader import dump_mapping, load_mapping


class TaskCatalog:
    """Load, validate, list, and persist registered step-based tasks."""

    def __init__(self, paths: list[Path] | None = None) -> None:
        self.paths = paths or [project_path("tasks", "demo_flow.yaml"), project_path("tasks", "omx_tasks.yaml")]
        self._tasks: dict[str, TaskDefinition] = {}
        self.reload()

    def reload(self) -> None:
        tasks: dict[str, TaskDefinition] = {}
        for path in self.paths:
            if not path.exists():
                continue
            data = load_mapping(path)
            for item in data.get("tasks", []):
                task = TaskDefinition.from_mapping(item)
                self.validate_task(task)
                tasks[task.name] = task
        self._tasks = tasks

    def list_tasks(self) -> list[TaskDefinition]:
        return list(self._tasks.values())

    def get(self, name: str) -> TaskDefinition | None:
        return self._tasks.get(name)

    def add_or_update(self, task: TaskDefinition, *, persist_path: Path | None = None) -> None:
        self.validate_task(task)
        self._tasks[task.name] = task
        if persist_path is not None:
            self.save(persist_path)

    def delete(self, name: str, *, persist: bool = False, persist_path: Path | None = None) -> bool:
        removed = self._tasks.pop(name, None) is not None
        if removed and persist:
            self.save(persist_path)
        return removed

    def export(self) -> dict[str, object]:
        return {"tasks": [task.to_mapping() for task in self.list_tasks()]}

    def save(self, path: Path | None = None) -> None:
        target = path or self.paths[-1]
        data = self.export()
        dump_mapping(target, data)

    def from_payload(self, payload: dict[str, object]) -> TaskDefinition:
        task = TaskDefinition.from_mapping(payload)
        self.validate_task(task)
        return task

    def validate_task(self, task: TaskDefinition) -> None:
        for step in task.steps:
            self.validate_step(step)

    def validate_step(self, step: TaskStep) -> None:
        if step.type == "move_l":
            for key in ("x", "y", "z"):
                if key not in step.params:
                    raise ValueError(f"move_l step requires {key}")
                float(step.params[key])
            if "duration" in step.params:
                duration = float(step.params["duration"])
                if duration <= 0:
                    raise ValueError("move_l duration must be positive")
        elif step.type == "gripper":
            command = step.params.get("command")
            if command not in {"open", "close"}:
                raise ValueError("gripper command must be 'open' or 'close'")
        elif step.type == "wait":
            duration = float(step.params.get("duration", 0))
            if duration < 0:
                raise ValueError("wait duration must be non-negative")
        elif step.type == "say":
            if not str(step.params.get("text", "")).strip():
                raise ValueError("say step requires text")
        else:
            raise ValueError(f"unsupported task step type: {step.type}")
