from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry


registry = DeviceRegistry()

# Each remote device references a connection profile.
assert registry.connection_id_for("ai_worker") == "ai_worker_jetson", registry.connection_id_for("ai_worker")
assert registry.connection_id_for("omy") == "omy_raspberry_pi", registry.connection_id_for("omy")
assert registry.connection_id_for("omx") == "omx_pc", registry.connection_id_for("omx")

# Structured command specs expose command_type/run_mode.
spec = registry.command_spec("ai_worker", "bringup_bg2")
assert spec is not None, "bringup_bg2 missing"
assert spec["command_type"] == "container", spec
assert spec["run_mode"] == "detached", spec
assert "ffw_bg2_ai.launch.py" in spec["command"], spec

host_spec = registry.command_spec("ai_worker", "container_start")
assert host_spec["command_type"] == "host", host_spec

# command_for stays backward compatible (returns the raw string).
assert registry.command_for("ai_worker", "bringup_bg2") == spec["command"]

# Unknown command_key is rejected (allowlist).
assert registry.command_spec("ai_worker", "rm_rf_root") is None
assert registry.command_for("ai_worker", "definitely_not_a_command") is None

# command_keys lists only registered keys.
keys = registry.command_keys("omy")
assert "play_demo_bag" in keys and "stop" in keys, keys

print("ok cli command interface")
