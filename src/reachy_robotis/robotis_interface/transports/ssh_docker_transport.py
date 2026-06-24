"""SSH Docker transport for remote robot command execution."""

from __future__ import annotations

import subprocess
import logging
from typing import Any

from reachy_robotis.robotis_interface.core.schemas import CommandDefinition, ActionResult
from reachy_robotis.robotis_interface.transports.return_codes import describe_return_code, tail_lines

logger = logging.getLogger(__name__)


class SSHDockerTransport:
    """Execute commands in remote Docker containers via SSH."""

    def __init__(
        self,
        device_id: str,
        host: str,
        user: str,
        container_name: str,
        ros_setup_paths: list[str] | None = None,
        working_directory: str = "/root",
        timeout_s: float = 30.0,
    ) -> None:
        """Initialize SSH Docker transport."""
        self.device_id = device_id
        self.host = host
        self.user = user
        self.container_name = container_name
        self.ros_setup_paths = ros_setup_paths or []
        self.working_directory = working_directory
        self.timeout_s = timeout_s
        self._last_error = ""

    def _build_command(self, cmd: str) -> str:
        """Build full SSH + Docker + ROS 2 setup command."""
        setup_commands = ""
        if self.ros_setup_paths:
            setup_list = [f"source {path}" for path in self.ros_setup_paths]
            setup_commands = " && ".join(setup_list) + " && "

        docker_cmd = f"docker exec {self.container_name} bash -c '{setup_commands}cd {self.working_directory} && {cmd}'"

        ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=5 {self.user}@{self.host} '{docker_cmd}'"

        return ssh_cmd

    def run_command(
        self,
        command: str,
        run_mode: str = "foreground",
        capture_output: bool = True,
    ) -> dict[str, Any]:
        """Execute command in remote Docker container."""
        try:
            ssh_cmd = self._build_command(command)

            logger.info(f"[{self.device_id}] Executing: {command}")
            logger.debug(f"[{self.device_id}] Full SSH command: {ssh_cmd}")

            if run_mode == "detached":
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

            result = subprocess.run(
                ssh_cmd,
                shell=True,
                capture_output=capture_output,
                timeout=self.timeout_s,
                text=True,
            )

            rc = result.returncode
            meaning = describe_return_code(rc)
            stdout_tail = tail_lines(result.stdout, 50)
            stderr_tail = tail_lines(result.stderr, 50)

            if rc == 0:
                return {
                    "ok": True,
                    "message": f"Command completed: {command}",
                    "output": stdout_tail,
                    "error": "",
                    "return_code": rc,
                    "return_meaning": meaning,
                }

            error_msg = stderr_tail or f"rc={rc} ({meaning})"
            self._last_error = error_msg
            return {
                "ok": False,
                "message": f"Command failed: {command} (rc={rc}, {meaning})",
                "output": stdout_tail,
                "error": error_msg,
                "return_code": rc,
                "return_meaning": meaning,
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
        """Async wrapper for run_command."""
        import asyncio

        result = await asyncio.to_thread(
            self.run_command,
            command,
            run_mode,
        )

        return ActionResult(
            ok=result["ok"],
            message=result["message"],
            error=None if result["ok"] else "ssh_docker_command_failed",
            data={
                "device": self.device_id,
                "command": command,
                "output": result["output"],
                "error": result["error"],
                "return_code": result.get("return_code"),
                "return_meaning": result.get("return_meaning", ""),
            },
        )

    def check_connectivity(self) -> dict[str, Any]:
        """Check SSH and Docker connectivity."""
        try:
            ssh_test = subprocess.run(
                f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=3 {self.user}@{self.host} 'echo ok'",
                shell=True,
                capture_output=True,
                timeout=5.0,
                text=True,
            )

            if ssh_test.returncode != 0:
                return {
                    "ok": False,
                    "ssh_connected": False,
                    "docker_connected": False,
                    "error": "SSH connection failed",
                }

            docker_test = subprocess.run(
                f"ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=3 {self.user}@{self.host} 'docker inspect {self.container_name} > /dev/null && echo ok'",
                shell=True,
                capture_output=True,
                timeout=5.0,
                text=True,
            )

            if docker_test.returncode != 0:
                return {
                    "ok": False,
                    "ssh_connected": True,
                    "docker_connected": False,
                    "error": f"Docker container {self.container_name} not found",
                }

            return {
                "ok": True,
                "ssh_connected": True,
                "docker_connected": True,
                "error": "",
            }

        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "ssh_connected": False,
                "docker_connected": False,
                "error": "Connection timeout",
            }

        except Exception as e:
            return {
                "ok": False,
                "ssh_connected": False,
                "docker_connected": False,
                "error": str(e),
            }

    def get_last_error(self) -> str:
        """Get last error message."""
        return self._last_error
