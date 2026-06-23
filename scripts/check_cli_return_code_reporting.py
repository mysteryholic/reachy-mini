from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.transports.return_codes import (
    describe_return_code,
    tail_lines,
)


# The three return codes from the failing OMX bringup must be explained.
assert "SSH" in describe_return_code(255), describe_return_code(255)
assert "terminated" in describe_return_code(143).lower(), describe_return_code(143)
killed = describe_return_code(137).lower()
assert "killed" in killed or "oom" in killed, killed

assert describe_return_code(0) == "success"
assert describe_return_code(None) == "still running"
assert "not found" in describe_return_code(127)

# tail_lines keeps only the last N lines for the log preview.
text = "\n".join(str(i) for i in range(200))
preview = tail_lines(text, 50)
lines = preview.splitlines()
assert len(lines) == 50, len(lines)
assert lines[0] == "150" and lines[-1] == "199", (lines[0], lines[-1])
assert tail_lines("", 50) == ""
assert tail_lines(None, 50) == ""

# SSHDockerTransport surfaces return_code/return_meaning fields.
import inspect

from reachy_robotis.robotis_interface.transports.ssh_docker_transport import SSHDockerTransport

src = inspect.getsource(SSHDockerTransport.run_command)
assert "return_code" in src and "return_meaning" in src, "ssh transport must report return codes"

# CLITransport records last_return_code / log tails.
from reachy_robotis.robotis_interface.transports.cli_transport import CLITransport

cli_src = inspect.getsource(CLITransport)
for field in ("last_return_code", "last_return_meaning", "last_stdout_tail", "last_stderr_tail"):
    assert field in cli_src, f"CLITransport missing {field}"

print("ok cli return code reporting")
