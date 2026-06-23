from __future__ import annotations

import time
import threading

from reachy_robotis.robotis_interface.core.schemas import DeviceStatus


class StatusStore:
    """Thread-safe status snapshots for all ROBOTIS-facing devices."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._devices: dict[str, DeviceStatus] = {}

    def ensure_device(self, device: str, *, mode: str = "mock", online: bool = False) -> DeviceStatus:
        with self._lock:
            status = self._devices.get(device)
            if status is None:
                status = DeviceStatus(device=device, mode=mode, online=online)
                self._devices[device] = status
            return status

    def seed_device(
        self,
        device: str,
        *,
        mode: str,
        configured: bool,
        online: bool,
        connection_status: str,
        host: str = "",
        container: str = "",
    ) -> DeviceStatus:
        """Seed a device's authoritative config-derived fields at startup.

        Unlike :meth:`ensure_device`, this overwrites ``mode``/``host``/etc.
        even if the device already exists, so config is always the source of
        truth and the top-level ``devices`` snapshot cannot drift from config.
        """
        with self._lock:
            status = self.ensure_device(device, mode=mode, online=online)
            status.mode = mode
            status.configured = configured
            status.online = online
            status.connection_status = connection_status
            status.host = host
            status.container = container
            status.updated_at = time.time()
            return status

    def update(
        self,
        device: str,
        *,
        mode: str | None = None,
        online: bool | None = None,
        connection_status: str | None = None,
        host: str | None = None,
        container: str | None = None,
        configured: bool | None = None,
        active_action: str | None | object = ...,
        message: str | None = None,
        error: str | None = None,
    ) -> DeviceStatus:
        with self._lock:
            status = self.ensure_device(device)
            if mode is not None:
                status.mode = mode
            if online is not None:
                status.online = online
            if connection_status is not None:
                status.connection_status = connection_status
            if host is not None:
                status.host = host
            if container is not None:
                status.container = container
            if configured is not None:
                status.configured = configured
            if active_action is not ...:
                status.active_action = active_action  # type: ignore[assignment]
            if message:
                status.append_log(message)
            if error is not None:
                status.last_error = error
            return status

    def snapshot(self) -> dict[str, dict[str, object]]:
        with self._lock:
            return {name: status.to_mapping() for name, status in self._devices.items()}

