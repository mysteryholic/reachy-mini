from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any

from reachy_robotis.robotis_interface.core.paths import project_path
from reachy_robotis.robotis_interface.core.yaml_loader import load_mapping


class ConnectionProfile:
    """Resolved SSH connection profile for one robot target."""

    def __init__(self, connection_id: str, data: dict[str, Any]) -> None:
        self.connection_id = connection_id
        self.display_name = str(data.get("display_name") or connection_id)
        self.target = str(data.get("target") or "")
        self.transport = str(data.get("transport") or "ssh_docker")
        self.host = str(data.get("host") or "")
        self.fallback_hosts = [str(h) for h in (data.get("fallback_hosts") or []) if str(h)]
        self.port = int(data.get("port") or 22)
        self.user = str(data.get("user") or "")
        auth = data.get("auth") or {}
        self.auth_method = str(auth.get("method") or "ssh_key")
        self.key_path = os.path.expanduser(str(auth.get("key_path") or "")) if auth.get("key_path") else ""
        self.password_env = str(auth.get("password_env") or "")
        self.connect_timeout_sec = int(data.get("connect_timeout_sec") or 5)
        self.command_timeout_sec = int(data.get("command_timeout_sec") or 30)
        self.working_dir = str(data.get("working_dir") or "")
        container = data.get("container") or {}
        self.container_mode = str(container.get("mode") or "docker_exec")
        self.container_name = str(container.get("name") or "")
        self.helper_script = str(container.get("helper_script") or "")
        self.exec_shell = str(container.get("exec_shell") or "bash -lc")
        ros = data.get("ros") or {}
        self.ros_distro = str(ros.get("distro") or "")
        self.ros_setup = [str(s) for s in (ros.get("setup") or []) if str(s)]
        self._raw = dict(data)

    def hosts_in_order(self) -> list[str]:
        """Primary host first, then fallbacks."""
        hosts = [self.host] if self.host else []
        hosts.extend(h for h in self.fallback_hosts if h)
        return hosts

    def to_public_mapping(self) -> dict[str, Any]:
        """Serializable view for UI/tools. Never includes secrets."""
        return {
            "connection_id": self.connection_id,
            "display_name": self.display_name,
            "target": self.target,
            "transport": self.transport,
            "host": self.host,
            "fallback_hosts": list(self.fallback_hosts),
            "port": self.port,
            "user": self.user,
            "auth_method": self.auth_method,
            "key_path": self.key_path,
            "password_env": self.password_env,  # the env var NAME, not the secret
            "connect_timeout_sec": self.connect_timeout_sec,
            "command_timeout_sec": self.command_timeout_sec,
            "working_dir": self.working_dir,
            "container_mode": self.container_mode,
            "container_name": self.container_name,
            "helper_script": self.helper_script,
            "exec_shell": self.exec_shell,
            "ros_distro": self.ros_distro,
            "ros_setup": list(self.ros_setup),
        }


class ConnectionRegistry:
    """Load and serve SSH connection profiles from robotis_connections.yaml."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or project_path("config", "robotis_connections.yaml")
        self._profiles: dict[str, ConnectionProfile] = {}
        self.reload()

    def reload(self) -> None:
        profiles: dict[str, ConnectionProfile] = {}
        if self.path.exists():
            data = load_mapping(self.path)
            raw = data.get("connections", {})
            if not isinstance(raw, dict):
                raise ValueError("connections must be a mapping")
            for cid, value in raw.items():
                profiles[str(cid)] = ConnectionProfile(str(cid), dict(value or {}))
        self._profiles = profiles

    def list_connections(self) -> dict[str, ConnectionProfile]:
        return dict(self._profiles)

    def get(self, connection_id: str) -> ConnectionProfile | None:
        return self._profiles.get(connection_id)

    def save_connection(self, connection_id: str, data: dict[str, Any]) -> ConnectionProfile:
        """Persist (add/update) one connection profile. Secrets are not accepted here."""
        from reachy_robotis.robotis_interface.core.yaml_loader import dump_mapping

        existing = load_mapping(self.path) if self.path.exists() else {"connections": {}}
        connections = existing.get("connections") or {}
        connections[connection_id] = data
        existing["connections"] = connections
        dump_mapping(self.path, existing)
        self.reload()
        profile = self.get(connection_id)
        assert profile is not None
        return profile

    def test_tcp(self, connection_id: str) -> dict[str, Any]:
        """Step 1: is the host TCP-reachable on the SSH port?"""
        profile = self.get(connection_id)
        if profile is None:
            return {"ok": False, "step": "tcp", "error": "unknown_connection"}
        last_error = "no_host_configured"
        for host in profile.hosts_in_order():
            try:
                with socket.create_connection((host, profile.port), timeout=profile.connect_timeout_sec):
                    return {"ok": True, "step": "tcp", "host": host, "port": profile.port}
            except Exception as exc:  # noqa: BLE001 - report any failure verbatim
                last_error = f"{type(exc).__name__}: {exc}"
        return {"ok": False, "step": "tcp", "error": last_error, "port": profile.port}
