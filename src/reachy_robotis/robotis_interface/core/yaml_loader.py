from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_mapping(path: Path) -> dict[str, Any]:
    """Load a YAML file, falling back to JSON-compatible YAML when PyYAML is absent."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text) or {}
    except ModuleNotFoundError:
        data = json.loads(text)

    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def dump_mapping(path: Path, data: dict[str, Any]) -> None:
    """Write a mapping as readable JSON, which is valid YAML too."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

