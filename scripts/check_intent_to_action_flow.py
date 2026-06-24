from __future__ import annotations

import os
import asyncio

import _bootstrap  # noqa: F401

os.environ["ROBOTIS_CLI_DRY_RUN"] = "1"

from reachy_robotis.robotis_interface.core.service import get_robotis_executor


executor = get_robotis_executor()

# English triggers must resolve to the right registered action.
cases = {
    "play AI Worker demo": "ai_worker_demo_command",
    "start AI Worker": "ai_worker_bg2",
    "play OMY demo": "omy_demo_bag",
    "start OMY leader mode": "omy_leader_follower",
    "push the box": "omx_push_box_custom",
    "stop all": "stop_all",
}
for text, expected in cases.items():
    match = executor.resolve(text)
    assert match.get("ok"), (text, match)
    assert match.get("kind") == "action", (text, match)
    assert match.get("name") == expected, (text, match, expected)


async def main() -> None:
    # Full flow: text -> action -> recipe -> terminal session (dry-run).
    result = await executor.run_resolved_text("play AI Worker demo")
    assert result.ok, result
    sessions = result.data.get("sessions", [])
    assert sessions and "ros2 bag play" in sessions[0]["command"], result.data

    # stop_all routes through stop() on all adapters.
    stop = await executor.run_resolved_text("stop all")
    assert stop.ok or stop.error is None, stop


asyncio.run(main())
print("ok intent to action flow")
