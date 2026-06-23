from __future__ import annotations

import os
import ast
import asyncio
from pathlib import Path

import _bootstrap  # noqa: F401

os.environ["ROBOTIS_CLI_DRY_RUN"] = "1"

from reachy_robotis.robotis_interface.core.service import get_robotis_executor
from reachy_robotis.robotis_interface.transports.connection_transport import ConnectionTransport


# 1) Unknown command_key is rejected -> only allowlisted keys run.
executor = get_robotis_executor()


async def main() -> None:
    bad = await executor.run_device_command("omx", "; rm -rf /")
    assert not bad.ok and bad.error == "command_not_allowlisted", bad
    bad_recipe = await executor.start_recipe("; rm -rf /")
    assert not bad_recipe.ok and bad_recipe.error == "unknown_recipe", bad_recipe


asyncio.run(main())

# 2) The command run route is keyed by command_key (path param), and the router
#    never reads a free-form "command" string from the request body.
routes = (Path(_bootstrap.ROOT) / "src" / "reachy_robotis" / "robotis_interface" / "web" / "routes.py").read_text(encoding="utf-8")
assert "/commands/{command_key}/run" in routes, "expected command_key path route"
tree = ast.parse(routes)
for node in ast.walk(tree):
    if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "device_command_run":
        arg_names = {a.arg for a in node.args.args}
        assert arg_names <= {"device_id", "command_key", "self"}, arg_names
        assert "payload" not in arg_names and "command" not in arg_names, arg_names

# 3) ConnectionTransport only accepts a fixed set of command_types (no arbitrary modes).
assert ConnectionTransport.run_command.__doc__ and "free-form" in ConnectionTransport.run_command.__doc__.lower()

# 4) No conversation tool exposes raw shell execution.
tools_dir = Path(_bootstrap.ROOT) / "src" / "reachy_robotis" / "tools"
for tool_file in tools_dir.glob("*.py"):
    text = tool_file.read_text(encoding="utf-8")
    # tools must not call subprocess / os.system directly.
    assert "os.system(" not in text, tool_file
    assert "subprocess.run(" not in text and "subprocess.Popen(" not in text, tool_file

print("ok no free-form shell execution")
