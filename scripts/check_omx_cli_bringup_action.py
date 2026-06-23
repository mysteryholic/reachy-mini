from __future__ import annotations

import os
import asyncio

import _bootstrap  # noqa: F401

os.environ["ROBOTIS_CLI_DRY_RUN"] = "1"

from reachy_robotis.robotis_interface.core.service import get_robotis_executor


executor = get_robotis_executor()


async def main() -> None:
    checks = {
        "start OMX AI": ("omx_bringup_ai", "bringup_ai", "omx_ai.launch.py"),
        "start OMX": ("omx_bringup_f", "bringup_f", "omx_f.launch.py"),
        "play OMX rosbag": ("omx_play_demo_bag", "play_demo_bag", "ros2 bag play /workspace/bags/omx_demo_motion"),
        "stop OMX": ("omx_stop", "stop", "pkill -TERM"),
    }
    for phrase, (action_name, command_key, command_text) in checks.items():
        resolved = executor.resolve(phrase)
        assert resolved["ok"] and resolved["kind"] == "action", resolved
        assert resolved["name"] == action_name, resolved
        result = await executor.run_action("action", action_name)
        assert result.ok, result
        if result.kind == "recipe":
            sessions = result.data.get("sessions", [])
            assert sessions, result.data
            assert command_text in sessions[0]["command"], sessions
            assert sessions[0]["run_mode"] in {"detached", "foreground"}, sessions
        else:
            assert result.data.get("run_mode") in {"detached", "foreground"}, result.data
            assert command_text in result.data.get("built_command", ""), result.data
            last = executor.last_command("omx")
            assert last["command_key"] == command_key, last


asyncio.run(main())
print("ok omx cli bringup action")
