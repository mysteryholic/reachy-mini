"""SSH local shell transport for remote robot command execution."""

from __future__ import annotations

import subprocess
import logging
from typing import Any

from reachy_robotis.robotis_interface.core.schemas import ActionResult

logger = logging.getLogger(__name__)


class SSHLocalTransport:
    """Execute commands in remote local shell via SSH."""

    def __init__(
        self,
        device_id: str,
        host: str,
        user: str,
        ros_setup_paths: list[str] | None = None,
        working_directory: str = "/root",
        timeout_s: float = 30.0,
    ) -> None:
        """
        Initialize SSH local transport.

        Args:
            device_id: Device identifier
            host: SSH host address
            user: SSH username
            ros_setup_paths: List of ROS 2 setup scripts to source
            working_directory: Working directory on remote
            timeout_s: Command timeout in seconds
        """
        self.device_id = device_id
        self.host = host
        self.user = user
        self.ros_setup_paths = ros_setup_paths or []
        self.working_directory = working_directory
        self.timeout_s = timeout_s
        self._last_error = ""

    def _build_command(self, cmd: str) -> str:
        """Build full SSH + ROS 2 setup command."""
        # Build ROS 2 setup string
        setup_commands = ""
        if self.ros_setup_paths:
            setup_list = [f"source {path}" for path in self.ros_setup_paths]
            setup_commands = " && ".join(setup_list) + " && "

        # Full command with bash
        full_cmd = f"{setup_commands}cd {self.working_directory} && {cmd}"

        # SSH wrapper
        ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {self.user}@{self.host} '{full_cmd}'"

        return ssh_cmd

    def run_command(
        self,
        command: str,
        run_mode: str = "foreground",
        capture_output: bool = True,
    ) -> dict[str, Any]:
        """
        Execute command in remote local shell.

        Args:
            command: Command to execute
            run_mode: 'foreground' or 'detached'
            capture_output: Whether to capture stdout/stderr

        Returns:
            Result dictionary with ok, message, output, error
        """
        try:
            ssh_cmd = self._build_command(command)

            logger.info(f"[{self.device_id}] Executing: {command}")
            logger.debug(f"[{self.device_id}] Full SSH command: {ssh_cmd}")

            if run_mode == "detached":
                # Start in background, don't wait
                subprocess.Popen(
                    ssh_cmd,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return {
                    "ok": True,
                    "message": f"Command started in background: {command}",
                    "output": "",
                    "error": "",
                }

            # Foreground: wait for completion
            result = subprocess.run(
                ssh_cmd,
                shell=True,
                capture_output=capture_output,
                timeout=self.timeout_s,
                text=True,
            )

            if result.returncode == 0:
                return {
                    "ok": True,
                    "message": f"Command completed: {command}",
                    "output": result.stdout,
                    "error": "",
                }

            error_msg = result.stderr or f"Exit code: {result.returncode}"
            self._last_error = error_msg
            return {
                "ok": False,
                "message": f"Command failed: {command}",
                "output": result.stdout,
                "error": error_msg,
            }

        except subprocess.TimeoutExpired:
            error_msg = f"Command timeout ({self.timeout_s}s)"
            self._last_error = error_msg
            return {
                "ok": False,
                "message": error_msg,
                "output": "",
                "error": error_msg,
            }

        except Exception as e:
            error_msg = f"SSH execution failed: {str(e)}"
            self._last_error = error_msg
            logger.error(f"[{self.device_id}] {error_msg}")
            return {
                "ok": False,
                "message": error_msg,
                "output": "",
                "error": error_msg,
            }

    async def async_run_command(
        self,
        command: str,
        run_mode: str = "foreground",
    ) -> ActionResult:
        """
        Async wrapper for run_command.

        Args:
            command: Command to execute
            run_mode: 'foreground' or 'detached'

        Returns:
            ActionResult
        """
        import asyncio

        result = await asyncio.to_thread(
            self.run_command,
            command,
            run_mode,
        )

        return ActionResult(
            ok=result["ok"],
            message=result["message"],
            data={
                "device": self.device_id,
                "command": command,
                "output": result["output"],
                "error": result["error"],
            },
        )

    def check_connectivity(self) -> dict[str, Any]:
        """Check SSH connectivity."""
        try:
            ssh_test = subprocess.run(
                f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 {self.user}@{self.host} 'echo ok'",
                shell=True,
                capture_output=True,
                timeout=5.0,
                text=True,
            )

            if ssh_test.returncode == 0:
                return {
                    "ok": True,
                    "ssh_connected": True,
                    "error": "",
                }

            return {
                "ok": False,
                "ssh_connected": False,
                "error": "SSH connection failed",
            }

        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "ssh_connected": False,
                "error": "Connection timeout",
            }

        except Exception as e:
            return {
                "ok": False,
                "ssh_connected": False,
                "error": str(e),
            }

    def get_last_error(self) -> str:
        """Get last error message."""
        return self._last_error
