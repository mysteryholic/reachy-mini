from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.transports.connection_transport import ConnectionTransport


registry = ConnectionRegistry()
profile = registry.get("omx_pc")

assert profile is not None, "omx_pc connection profile is missing"
assert profile.display_name == "OMX Control PC", profile.display_name
assert profile.target == "omx", profile.target
assert profile.transport == "ssh_docker", profile.transport
assert profile.host == "192.168.60.74", profile.host
assert profile.port == 22, profile.port
assert profile.user == "robotis", profile.user
assert profile.auth_method == "ssh_key", profile.auth_method
assert profile.key_path.endswith(".ssh/id_ed25519"), profile.key_path
assert profile.password_env == "OMX_SSH_PASSWORD", profile.password_env
assert profile.working_dir == "~/ros2_ws", profile.working_dir
assert profile.container_mode == "docker_exec", profile.container_mode
assert profile.container_name == "open_manipulator", profile.container_name
assert profile.exec_shell == "bash -lc", profile.exec_shell
assert profile.ros_distro == "jazzy", profile.ros_distro
assert profile.ros_setup == [
    "source /opt/ros/jazzy/setup.bash",
    "source /root/ros2_ws/install/setup.bash",
], profile.ros_setup

built = ConnectionTransport(profile).build_command(
    "ros2 launch open_manipulator_bringup omx_f.launch.py",
    "container",
    "detached",
)
assert "robotis@192.168.60.74" in built, built
assert "docker exec -d open_manipulator" in built, built
assert "source /opt/ros/jazzy/setup.bash" in built, built
assert "source /root/ros2_ws/install/setup.bash" in built, built

print("ok omx connection profile")
