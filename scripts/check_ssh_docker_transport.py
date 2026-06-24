from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.transports.connection_transport import ConnectionTransport


registry = ConnectionRegistry()

# OMX docker_exec container command.
omx = ConnectionTransport(registry.get("omx_pc"))
built = omx.build_command("ros2 launch open_manipulator_bringup omx_f.launch.py", "container", "detached")
assert "ssh" in built and "robotis@192.168.60.74" in built, built
assert "docker exec -d open_manipulator" in built, built
assert "source /opt/ros/jazzy/setup.bash" in built, built
assert "ros2 launch open_manipulator_bringup omx_f.launch.py" in built, built
assert "cd ~/open_manipulator" in built, built  # leading ~ preserved for remote expansion
assert "cd '~/open_manipulator'" not in built, built

# AI Worker helper_script container command.
ai = ConnectionTransport(registry.get("ai_worker_jetson"))
built_ai = ai.build_command("ros2 launch ffw_bringup ffw_bg2_ai.launch.py", "container", "detached")
assert "./docker/container.sh exec" in built_ai, built_ai
assert "ai_worker" not in built_ai or "container.sh" in built_ai, built_ai
assert "-i" in built_ai and ".ssh" in built_ai, built_ai  # key path passed

# Host command (no ROS source, no docker).
built_host = ai.build_command("./docker/container.sh start", "host", "foreground")
assert "docker exec" not in built_host, built_host
assert "source /opt/ros" not in built_host, built_host
assert "./docker/container.sh start" in built_host, built_host

# dry_run never executes and returns the built command.
result = omx.run_command("ros2 topic list", "container", "foreground", dry_run=True)
assert result["ok"] and result["dry_run"], result
assert "docker exec" in result["built_command"], result
assert result["stdout_tail"] == "" and result["stderr_tail"] == "", result

print("ok ssh docker transport")
