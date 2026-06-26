from __future__ import annotations

import os
import json
import tempfile
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
    """Write a mapping as readable JSON (valid YAML too), atomically.

    Writes to a temp file in the same directory and ``os.replace``s it into
    place, so an interrupted or out-of-disk write can never truncate or corrupt
    the existing file (the previous data survives instead of being lost).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

