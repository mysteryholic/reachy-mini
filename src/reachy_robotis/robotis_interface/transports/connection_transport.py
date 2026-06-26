"""Generic SSH command transport driven by a ConnectionProfile."""

from __future__ import annotations

import shlex
import asyncio
import os
import subprocess
import tempfile
from typing import Any

from reachy_robotis.robotis_interface.core.schemas import ActionResult
from reachy_robotis.robotis_interface.core.connection_registry import ConnectionProfile
from reachy_robotis.robotis_interface.transports.return_codes import describe_return_code, tail_lines


VALID_COMMAND_TYPES = {"host", "container"}
VALID_RUN_MODES = {"foreground", "detached"}


class ConnectionTransport:
    """Build and run allowlisted commands against one ConnectionProfile."""

    def __init__(self, profile: ConnectionProfile) -> None:
        self.profile = profile

    def _container_exec(self, command: str, *, detached: bool = False) -> str:
        """Wrap a command to run inside the container with ROS sourced."""
        p = self.profile
        environment = [f"export {key}={shlex.quote(value)}" for key, value in p.ros_env.items()]
        setup = [*environment, *p.ros_setup]
        ros_command = " && ".join([*setup, command]) if setup else command
        exec_shell_parts = shlex.split(p.exec_shell or "bash -lc")
        if p.container_mode == "docker_exec":
            if not p.container_name:
                raise ValueError(f"{p.connection_id}: docker_exec requires container.name")
            args = ["docker", "exec"]
            if detached:
                args.append("-d")
            args.extend([p.container_name, *exec_shell_parts, ros_command])
        elif p.container_mode == "helper_script":
            if not p.helper_script:
                raise ValueError(f"{p.connection_id}: helper_script mode requires container.helper_script")
            args = [*shlex.split(p.helper_script), "exec", *exec_shell_parts, ros_command]
        elif p.container_mode == "none":
            ros_command = " && ".join([*p.ros_setup, command]) if p.ros_setup else command
            return ros_command
        else:
            raise ValueError(f"{p.connection_id}: unknown container.mode {p.container_mode!r}")
        return shlex.join(args)

    @staticmethod
    def _quote_remote_dir(path: str) -> str:
        """Quote a remote directory while preserving a leading ``~`` for shell expansion."""
        if path == "~":
            return "~"
        if path.startswith("~/"):
            return "~/" + shlex.quote(path[2:])
        return shlex.quote(path)

    def _remote_payload(self, command: str, command_type: str, run_mode: str) -> str:
        p = self.profile
        if command_type == "host":
            launch = command
        elif command_type == "container":
            launch = self._container_exec(command, detached=run_mode == "detached")
        else:
            raise ValueError(f"invalid command_type {command_type!r}")

        parts: list[str] = []
        if p.working_dir:
            parts.append(f"cd {self._quote_remote_dir(p.working_dir)}")
        if run_mode == "detached" and not (command_type == "container" and p.container_mode == "docker_exec"):
            parts.append(f"nohup {launch} >/dev/null 2>&1 & echo detached pid=$!")
        else:
            parts.append(launch)
        return " && ".join(parts)

    def build_argv(self, command: str, command_type: str = "container", run_mode: str = "foreground", *, host: str | None = None) -> list[str]:
        """Return the full local argv (no shell) for running ``command`` remotely."""
        if command_type not in VALID_COMMAND_TYPES:
            raise ValueError(f"invalid command_type {command_type!r}")
        if run_mode not in VALID_RUN_MODES:
            raise ValueError(f"invalid run_mode {run_mode!r}")
        p = self.profile
        target_host = host or p.host
        if not target_host:
            raise ValueError(f"{p.connection_id}: no host configured")
        argv = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", f"ConnectTimeout={p.connect_timeout_sec}",
            "-p", str(p.port),
        ]
        if p.auth_method in {"password", "password_env"}:
            argv += [
                "-o", "BatchMode=no",
                "-o", "PreferredAuthentications=password,keyboard-interactive",
                "-o", "PubkeyAuthentication=no",
                "-o", "NumberOfPasswordPrompts=1",
            ]
        else:
            argv += ["-o", "BatchMode=yes"]
        key_path = p.expanded_key_path or p.key_path
        if key_path and p.auth_method not in {"password", "password_env"}:
            argv += ["-i", key_path]
        argv.append(f"{p.user}@{target_host}" if p.user else target_host)
        argv.append(self._remote_payload(command, command_type, run_mode))
        return argv

    def build_command(self, command: str, command_type: str = "container", run_mode: str = "foreground") -> str:
        """Human-readable rendering of the argv (for preview/tests)."""
        return shlex.join(self.build_argv(command, command_type, run_mode))

    def _subprocess_environment(self) -> tuple[dict[str, str] | None, str | None]:
        """Build a one-use SSH_ASKPASS environment without placing secrets in argv."""
        if self.profile.auth_method not in {"password", "password_env"}:
            return None, None
        password = self.profile.password()
        if not password and not self.profile.has_password:
            raise ValueError("Password authentication is selected, but no password was provided.")
        handle = tempfile.NamedTemporaryFile("w", prefix="reachy_askpass_", suffix=".sh", delete=False)
        try:
            handle.write("#!/bin/sh\nprintf '%s\\n' \"$REACHY_SSH_PASSWORD\"\n")
            handle.close()
            os.chmod(handle.name, 0o700)
        except Exception:
            try:
                os.unlink(handle.name)
            except OSError:
                pass
            raise
        env = os.environ.copy()
        env.update(
            {
                "SSH_ASKPASS": handle.name,
                "SSH_ASKPASS_REQUIRE": "force",
                "DISPLAY": env.get("DISPLAY") or "reachy:0",
                "REACHY_SSH_PASSWORD": password,
            }
        )
        return env, handle.name

    def run_command(
        self,
        command: str,
        command_type: str = "container",
        run_mode: str = "foreground",
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Execute one resolved command string. Never accepts free-form shell."""
        try:
            argv = self.build_argv(command, command_type, run_mode)
        except ValueError as exc:
            return {"ok": False, "error": "command_build_failed", "message": str(exc)}

        built = shlex.join(argv)
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "built_command": built,
                "command": command,
                "command_type": command_type,
                "run_mode": run_mode,
                "return_code": 0,
                "return_meaning": describe_return_code(0),
                "output": "",
                "error": "",
                "stdout_tail": "",
                "stderr_tail": "",
                "message": "Command preview built",
            }

        p = self.profile
        askpass_path: str | None = None
        try:
            env, askpass_path = self._subprocess_environment()
            if run_mode == "detached":
                proc = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=p.connect_timeout_sec + 10,
                    stdin=subprocess.DEVNULL,
                    env=env,
                )
                rc = proc.returncode
                return {
                    "ok": rc == 0,
                    "built_command": built,
                    "command": command,
                    "command_type": command_type,
                    "run_mode": run_mode,
                    "return_code": rc,
                    "return_meaning": describe_return_code(rc),
                    "output": tail_lines(proc.stdout, 50),
                    "error": tail_lines(proc.stderr, 50),
                    "stdout_tail": tail_lines(proc.stdout, 50),
                    "stderr_tail": tail_lines(proc.stderr, 50),
                    "message": "Command submitted" if rc == 0 else f"Command submission failed rc={rc}",
                }
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=p.command_timeout_sec,
                stdin=subprocess.DEVNULL,
                env=env,
            )
            rc = proc.returncode
            return {
                "ok": rc == 0,
                "built_command": built,
                "command": command,
                "command_type": command_type,
                "run_mode": run_mode,
                "return_code": rc,
                "return_meaning": describe_return_code(rc),
                "output": tail_lines(proc.stdout, 50),
                "error": tail_lines(proc.stderr, 50),
                "stdout_tail": tail_lines(proc.stdout, 50),
                "stderr_tail": tail_lines(proc.stderr, 50),
                "message": "Command completed" if rc == 0 else f"Command failed rc={rc}",
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "built_command": built,
                "command": command,
                "error": f"timeout after {p.command_timeout_sec}s",
                "return_code": 124,
                "return_meaning": describe_return_code(124),
                "output": "",
                "stdout_tail": "",
                "stderr_tail": f"timeout after {p.command_timeout_sec}s",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "built_command": built,
                "command": command,
                "error": f"{type(exc).__name__}: {exc}",
                "output": "",
                "stdout_tail": "",
                "stderr_tail": f"{type(exc).__name__}: {exc}",
            }
        finally:
            if askpass_path:
                try:
                    os.unlink(askpass_path)
                except OSError:
                    pass

    async def async_run_command(
        self,
        command: str,
        command_type: str = "container",
        run_mode: str = "foreground",
        *,
        dry_run: bool = False,
    ) -> ActionResult:
        result = await asyncio.to_thread(self.run_command, command, command_type, run_mode, dry_run=dry_run)
        return ActionResult(
            ok=bool(result.get("ok")),
            message=result.get("message") or ("dry-run" if result.get("dry_run") else f"command {run_mode}"),
            error=None if result.get("ok") else str(result.get("error") or "command_failed"),
            data=result,
        )
