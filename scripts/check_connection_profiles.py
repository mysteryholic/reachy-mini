from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry


registry = ConnectionRegistry()
connections = registry.list_connections()

for cid in ("ai_worker_jetson", "omy_raspberry_pi", "omx_pc"):
    assert cid in connections, (cid, list(connections))

ai = registry.get("ai_worker_jetson")
assert ai is not None
assert ai.host == "192.168.50.57", ai.host
assert ai.fallback_hosts == ["ffw-SNPR48A0000.local"], ai.fallback_hosts
assert ai.user == "robotis", ai.user
assert ai.container_mode == "helper_script", ai.container_mode
assert ai.helper_script == "./docker/container.sh", ai.helper_script
assert ai.ros_setup, ai.ros_setup
# key_path is expanded locally (~ resolved).
assert "~" not in ai.key_path, ai.key_path
assert ai.hosts_in_order() == ["192.168.50.57", "ffw-SNPR48A0000.local"], ai.hosts_in_order()

omy = registry.get("omy_raspberry_pi")
assert omy.container_mode == "docker_exec", omy.container_mode
assert omy.container_name == "omy_ros2", omy.container_name

# Public mapping must not leak secrets (only the env var NAME).
public = ai.to_public_mapping()
assert public["password_env"] == "AI_WORKER_SSH_PASSWORD", public
assert "password" not in {k.lower() for k in public} or public.get("password_env"), public
assert "auth" not in public  # no raw auth block

# save_connection round-trips.
print("ok connection profiles")
