from __future__ import annotations

from pathlib import Path
from typing import Any

from reachy_robotis.robotis_interface.core.paths import project_path
from reachy_robotis.robotis_interface.core.yaml_loader import load_mapping


class DeviceRegistry:
    """Device configuration and CLI allowlist registry."""

    def __init__(self, path: Path | None = None, overlay_paths: list[Path] | None = None) -> None:
        self.path = path or project_path("config", "robotis_devices.yaml")
        self.overlay_paths = overlay_paths or [
            project_path("config", "robotis_omy_raspberry_pi.yaml"),
            project_path("config", "robotis_ai_worker_jetson.yaml"),
        ]
        self._devices: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        if not self.path.exists():
            self._devices = {}
            return
        data = load_mapping(self.path)
        devices = self._extract_devices(data)
        for overlay_path in self.overlay_paths:
            if overlay_path.exists():
                overlay = self._extract_devices(load_mapping(overlay_path))
                for name, value in overlay.items():
                    merged = dict(devices.get(name, {}))
                    merged.update(value)
                    devices[name] = merged
        self._devices = {str(name): dict(value or {}) for name, value in devices.items()}

    def _extract_devices(self, data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        devices = data.get("devices", {})
        if not isinstance(devices, dict):
            raise ValueError("devices must be a mapping")
        return {str(name): dict(value or {}) for name, value in devices.items()}

    def list_devices(self) -> dict[str, dict[str, Any]]:
        return dict(self._devices)

    def get(self, device: str) -> dict[str, Any]:
        return dict(self._devices.get(device, {}))

    def mode_for(self, device: str) -> str:
        return str(self.get(device).get("mode") or "mock")

    def enabled(self, device: str) -> bool:
        return bool(self.get(device).get("enabled", True))

    def connection_id_for(self, device: str) -> str | None:
        cid = self.get(device).get("connection_id")
        return str(cid) if cid else None

    def command_keys(self, device: str) -> list[str]:
        commands = self.get(device).get("commands", {})
        return sorted(commands.keys()) if isinstance(commands, dict) else []

    def command_spec(self, device: str, command_key: str) -> dict[str, Any] | None:
        """Return the full structured spec for a command_key, or None."""
        commands = self.get(device).get("commands", {})
        if not isinstance(commands, dict):
            return None
        value = commands.get(command_key)
        if value is None:
            return None
        if isinstance(value, dict):
            return {
                "command_key": command_key,
                "display_name": str(value.get("display_name") or command_key),
                "command_type": str(value.get("command_type") or "container"),
                "command": str(value.get("command") or ""),
                "run_mode": str(value.get("run_mode") or "foreground"),
            }
        return {
            "command_key": command_key,
            "display_name": command_key,
            "command_type": "container",
            "command": str(value),
            "run_mode": "foreground",
        }

    def command_for(self, device: str, command_key: str) -> str | None:
        """Return only the raw command string (backward compatible)."""
        spec = self.command_spec(device, command_key)
        return spec["command"] if spec and spec["command"] else None
