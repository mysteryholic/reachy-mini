"""Human-readable interpretation of process/SSH return codes for the UI."""

from __future__ import annotations


def describe_return_code(rc: int | None) -> str:
    """Return a short English explanation for a process return code."""
    if rc is None:
        return "still running"
    if rc == 0:
        return "success"
    if rc == 124:
        return "timeout (command exceeded its time limit)"
    if rc == 125:
        return "docker run failure"
    if rc == 126:
        return "command found but not executable"
    if rc == 127:
        return "command not found"
    if rc == 137:
        return "killed (SIGKILL; possible OOM or `docker kill`)"
    if rc == 143:
        return "terminated (SIGTERM)"
    if rc == 255:
        return "SSH/remote command failure (connection or remote exit 255)"
    if 128 < rc < 165:
        return f"terminated by signal {rc - 128}"
    return f"exit code {rc}"


def tail_lines(text: str | None, lines: int = 50) -> str:
    """Return the last ``lines`` lines of ``text`` for a compact log preview."""
    if not text:
        return ""
    return "\n".join(text.splitlines()[-lines:])
