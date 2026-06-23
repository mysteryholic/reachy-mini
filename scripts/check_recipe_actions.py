from __future__ import annotations

import os
import asyncio

import _bootstrap  # noqa: F401

os.environ["ROBOTIS_CLI_DRY_RUN"] = "1"

from reachy_robotis.robotis_interface.core.service import get_robotis_executor


async def main() -> None:
    executor = get_robotis_executor()
    for phrase, action_name, recipe_id in (
        ("start OMX MoveIt", "omx_moveit", "omx_moveit"),
        ("start OMY MoveIt", "omy_moveit", "omy_moveit"),
        ("play OMX rosbag", "omx_play_demo_bag", "omx_play_demo_bag"),
    ):
        resolved = executor.resolve(phrase)
        assert resolved["ok"] and resolved["kind"] == "action", resolved
        assert resolved["name"] == action_name, resolved
        result = await executor.run_action("action", action_name)
        assert result.ok and result.data["recipe_id"] == recipe_id, result


asyncio.run(main())
print("ok recipe actions")
