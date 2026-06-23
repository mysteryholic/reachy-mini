from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry


registry = DeviceRegistry()
omx = registry.get("omx")

assert omx.get("display_name") == "OMX", omx
assert omx.get("connection_id") == "omx_pc", omx
assert omx.get("bridge_url") == "http://192.168.60.74:18001", omx

expected = {
    "bringup_ai": "ros2 launch open_manipulator_bringup omx_ai.launch.py",
    "bringup_f": "ros2 launch open_manipulator_bringup omx_f.launch.py",
    "moveit": "ros2 launch open_manipulator_moveit_config omx_f_moveit.launch.py",
    "gui": "ros2 launch open_manipulator_gui omx_f_gui.launch.py",
    "keyboard_teleop": "ros2 run open_manipulator_teleop omx_f_teleop",
    "play_demo_bag": "ros2 bag play /workspace/bags/omx_demo_motion",
    "status_topics": "ros2 topic list | head -80",
    "status_nodes": "ros2 node list | head -80",
    "stop": "pkill -TERM -f 'open_manipulator|omx_|omx_f|omx_ai|ros2 launch|ros2 bag play' || true",
    "kill": "pkill -KILL -f 'open_manipulator|omx_|omx_f|omx_ai|ros2 launch|ros2 bag play' || true",
}

for key, command in expected.items():
    spec = registry.command_spec("omx", key)
    assert spec is not None, f"missing OMX command {key}"
    assert spec["command_type"] == "container", spec
    assert spec["command"] == command, spec
    expected_mode = "foreground" if key in {"status_topics", "status_nodes", "stop", "kill"} else "detached"
    assert spec["run_mode"] == expected_mode, spec

print("ok omx cli bringup config")
