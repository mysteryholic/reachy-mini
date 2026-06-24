from __future__ import annotations

import os
import shlex
import asyncio
from asyncio.subprocess import Process

from reachy_robotis.robotis_interface.core.schemas import ActionResult, CommandDefinition
from reachy_robotis.robotis_interface.core.status_store import StatusStore
from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry
from reachy_robotis.robotis_interface.transports.return_codes import describe_return_code, tail_lines


class CLITransport:
    """Allowlisted local/SSH/SSH+Docker process launcher for CLI-controlled devices."""

    def __init__(self, device: str, registry: DeviceRegistry, status_store: StatusStore) -> None:
        self.device = device
        self.registry = registry
        self.status_store = status_store
        self._process: Process | None = None
        self._active_command: str | None = None
        self.last_return_code: int | None = None
        self.last_return_meaning: str = ""
        self.last_stdout_tail: str = ""
        self.last_stderr_tail: str = ""

    async def run(self, command: CommandDefinition) -> ActionResult:
        configured = self.registry.command_for(self.device, command.command_key)
        if not configured:
            return ActionResult(
                ok=False,
                kind="command",
                name=command.name,
                error="command_not_allowlisted",
                message=f"{self.device}:{command.command_key} is not in the allowlist.",
            )
        if self._process and self._process.returncode is None:
            return ActionResult(
                ok=False,
                kind="command",
                name=command.name,
                error="command_already_running",
                message="A CLI command is already running.",
                data={"active_command": self._active_command},
            )

        config = self.registry.get(self.device)
        dry_run_env = os.getenv("ROBOTIS_CLI_DRY_RUN")
        dry_run = dry_run_env != "0" if dry_run_env is not None else bool(config.get("dry_run", True))
        self._active_command = command.name
        self.status_store.update(self.device, active_action=command.name, message=f"CLI allowlisted: {command.command_key}")

        try:
            args = self._build_args(config, configured)
        except ValueError as exc:
            self._active_command = None
            self.status_store.update(self.device, active_action=None, error=str(exc), message=f"CLI config error: {exc}")
            return ActionResult(
                ok=False,
                kind="command",
                name=command.name,
                error="cli_config_error",
                message=str(exc),
                data={"stage": "build_args", "device": self.device, "command_key": command.command_key},
            )

        if dry_run:
            self.status_store.update(self.device, active_action=None, message=f"DRY RUN {self.device}: {' '.join(args)}")
            self._active_command = None
            return ActionResult(
                ok=True,
                kind="command",
                name=command.name,
                message=f"{command.display_name} dry-run completed",
                data={"dry_run": True, "command_key": command.command_key, "mode": config.get("mode"), "args": args},
            )

        try:
            self._process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            self._active_command = None
            self.status_store.update(self.device, active_action=None, error=str(exc), message=f"CLI spawn failed: {exc}")
            return ActionResult(
                ok=False,
                kind="command",
                name=command.name,
                error="cli_spawn_failed",
                message=str(exc),
                data={"stage": "spawn", "args": args},
            )
        except OSError as exc:
            self._active_command = None
            self.status_store.update(self.device, active_action=None, error=str(exc), message=f"CLI transport failed: {exc}")
            return ActionResult(
                ok=False,
                kind="command",
                name=command.name,
                error="cli_transport_failed",
                message=str(exc),
                data={"stage": "spawn", "args": args},
            )
        asyncio.create_task(self._collect_output(command.name, self._process))
        return ActionResult(
            ok=True,
            kind="command",
            name=command.name,
            message=f"{command.display_name} started",
            data={"pid": self._process.pid, "mode": config.get("mode"), "args": args},
        )

    async def stop(self) -> ActionResult:
        stop_command = self.registry.command_for(self.device, "stop")
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        if stop_command:
            config = self.registry.get(self.device)
            dry_run_env = os.getenv("ROBOTIS_CLI_DRY_RUN")
            dry_run = dry_run_env != "0" if dry_run_env is not None else bool(config.get("dry_run", True))
            if not dry_run:
                proc = await asyncio.create_subprocess_exec(*self._build_args(config, stop_command))
                await proc.wait()
            self.status_store.update(self.device, message=f"CLI stop allowlisted: {stop_command}")
        self._active_command = None
        self.status_store.update(self.device, active_action=None, message=f"{self.device} CLI stopped")
        return ActionResult(ok=True, message=f"{self.device} CLI Soft Stop")

    def _build_args(self, config: dict[str, object], command: str) -> list[str]:
        mode = str(config.get("cli_mode") or config.get("mode") or "local").strip()
        launch_command = self._wrap_ros_setup(config, command)
        if mode == "ssh_docker":
            launch_command = self._wrap_docker_exec(config, launch_command)

        host = str(config.get("host") or "").strip()
        user = str(config.get("user") or "").strip()
        if mode in {"ssh", "ssh_docker"} or (host and host not in {"localhost", "127.0.0.1"}):
            target = f"{user}@{host}" if user else host
            return ["ssh", target, "bash", "-lc", shlex.quote(launch_command)]
        if mode == "local_shell" or "source " in launch_command:
            return ["bash", "-lc", launch_command]
        return shlex.split(launch_command)

    def preview_command(self, command_key: str) -> dict[str, object]:
        configured = self.registry.command_for(self.device, command_key)
        if not configured:
            return {"ok": False, "error": "command_not_allowlisted", "device": self.device, "command_key": command_key}
        config = self.registry.get(self.device)
        return {
            "ok": True,
            "device": self.device,
            "mode": config.get("mode"),
            "host": config.get("host"),
            "container_name": config.get("container_name"),
            "ros_setup_path": config.get("ros_setup_path"),
            "ros_setup_paths": config.get("ros_setup_paths"),
            "args": self._build_args(config, configured),
        }

    def _wrap_ros_setup(self, config: dict[str, object], command: str) -> str:
        setup_paths = self._ros_setup_paths(config)
        working_directory = str(config.get("working_directory") or "").strip()
        parts: list[str] = []
        if working_directory:
            parts.append(f"cd {shlex.quote(working_directory)}")
        for setup_path in setup_paths:
            parts.append(f"source {shlex.quote(setup_path)}")
        parts.append(command)
        return " && ".join(parts)

    def _ros_setup_paths(self, config: dict[str, object]) -> list[str]:
        configured_paths = config.get("ros_setup_paths")
        if isinstance(configured_paths, list):
            return [str(path).strip() for path in configured_paths if str(path).strip()]
        setup_path = str(config.get("ros_setup_path") or "").strip()
        return [setup_path] if setup_path else []

    def _wrap_docker_exec(self, config: dict[str, object], command: str) -> str:
        container_name = str(config.get("container_name") or "").strip()
        if not container_name:
            raise ValueError(f"{self.device} ssh_docker mode requires container_name")
        docker_user = str(config.get("docker_user") or "").strip()
        exec_args = ["docker", "exec"]
        if docker_user:
            exec_args.extend(["-u", docker_user])
        exec_args.extend([container_name, "bash", "-lc", command])
        return " ".join(shlex.quote(part) for part in exec_args)

    async def _collect_output(self, command_name: str, process: Process) -> None:
        stdout, stderr = await process.communicate()
        stdout_text = stdout.decode(errors="replace") if stdout else ""
        stderr_text = stderr.decode(errors="replace") if stderr else ""
        rc = process.returncode
        meaning = describe_return_code(rc)

        self.last_return_code = rc
        self.last_return_meaning = meaning
        self.last_stdout_tail = tail_lines(stdout_text, 50)
        self.last_stderr_tail = tail_lines(stderr_text, 50)

        if self.last_stdout_tail:
            self.status_store.update(self.device, message=f"[stdout tail]\n{self.last_stdout_tail}")
        if self.last_stderr_tail:
            self.status_store.update(self.device, error=f"[stderr tail]\n{self.last_stderr_tail}")
        if rc:
            self.status_store.update(
                self.device,
                error=f"cli_command_failed rc={rc} ({meaning})",
                message=f"CLI command failed: {command_name} rc={rc} ({meaning})",
            )
        self.status_store.update(
            self.device,
            active_action=None,
            message=f"CLI command exited: {command_name} rc={rc} ({meaning})",
        )
        self._active_command = None
