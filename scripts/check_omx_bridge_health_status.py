from __future__ import annotations

import asyncio

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.status_store import StatusStore
from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry
from reachy_robotis.robotis_interface.adapters.omx_adapter import OMXAdapter


registry = DeviceRegistry()
status = StatusStore()

# Point OMX at an unreachable bridge port to force connection refused.
omx_config = registry.get("omx")
omx_config["mode"] = "bridge"
omx_config["bridge_host"] = "127.0.0.1"
omx_config["bridge_port"] = 65500  # very likely closed
registry._devices["omx"] = omx_config  # noqa: SLF001

adapter = OMXAdapter(status_store=status, registry=registry)

# After init the bridge is not reachable -> must not be online.
snap = status.snapshot()["omx"]
assert snap["online"] is False, snap
assert snap["connection_status"] in {"offline", "not_checked"}, snap

# A live probe against the closed port must report offline with an error.
result = asyncio.run(adapter.probe())
snap = status.snapshot()["omx"]
assert snap["online"] is False, snap
assert snap["connection_status"] == "offline", snap
assert snap["last_error"], "expected a connection error to be recorded"

print("ok omx bridge health status")
