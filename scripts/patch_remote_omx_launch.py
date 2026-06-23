from __future__ import annotations

from pathlib import Path


LAUNCH_PATHS = [
    Path("/root/ros2_ws/src/open_manipulator/open_manipulator_playground/launch/omx_hand_teleop.launch.py"),
    Path("/root/ros2_ws/install/open_manipulator_playground/share/open_manipulator_playground/launch/omx_hand_teleop.launch.py"),
]


def patch_launch(path: Path) -> None:
    text = path.read_text()
    backup = path.with_suffix(path.suffix + ".bak.reachy_robotis")
    if not backup.exists():
        backup.write_text(text)

    if "skill_republish_rate = LaunchConfiguration('skill_republish_rate')" not in text:
        text = text.replace(
            "    skill_pose_config = LaunchConfiguration('skill_pose_config')\n",
            "    skill_pose_config = LaunchConfiguration('skill_pose_config')\n"
            "    skill_settle_margin = LaunchConfiguration('skill_settle_margin')\n"
            "    skill_republish_rate = LaunchConfiguration('skill_republish_rate')\n"
            "    skill_command_time_from_start = LaunchConfiguration('skill_command_time_from_start')\n",
        )

    if "'skill_republish_rate': ParameterValue(skill_republish_rate, value_type=float)" not in text:
        text = text.replace(
            "            'skill_pose_config': skill_pose_config,\n",
            "            'skill_pose_config': skill_pose_config,\n"
            "            'skill_settle_margin': ParameterValue(skill_settle_margin, value_type=float),\n"
            "            'skill_republish_rate': ParameterValue(skill_republish_rate, value_type=float),\n"
            "            'skill_command_time_from_start': ParameterValue(\n"
            "                skill_command_time_from_start, value_type=float),\n",
        )

    if "DeclareLaunchArgument('skill_republish_rate'" not in text:
        text = text.replace(
            "        DeclareLaunchArgument('start_rviz', default_value='false'),\n",
            "        DeclareLaunchArgument('skill_settle_margin', default_value='0.30'),\n"
            "        DeclareLaunchArgument('skill_republish_rate', default_value='25.0'),\n"
            "        DeclareLaunchArgument('skill_command_time_from_start', default_value='0.12'),\n"
            "        DeclareLaunchArgument('start_rviz', default_value='false'),\n",
        )

    path.write_text(text)
    print(f"patched {path}")


def main() -> None:
    for launch_path in LAUNCH_PATHS:
        patch_launch(launch_path)


if __name__ == "__main__":
    main()
