from __future__ import annotations

from reachy_robotis.robotis_interface.adapters.base import RobotAdapter
from reachy_robotis.robotis_interface.core.schemas import ActionResult, CommandDefinition
from reachy_robotis.robotis_interface.core.status_store import StatusStore
from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry
from reachy_robotis.robotis_interface.transports.ssh_docker_transport import SSHDockerTransport


class AIWorkerAdapter(RobotAdapter):
    """SSH Docker relay adapter for AI Worker (Jetson Orin 32GB)."""

    def __init__(
        self,
        *,
        status_store: StatusStore,
        registry: DeviceRegistry,
    ) -> None:
        super().__init__(device="ai_worker", status_store=status_store)
        self.registry = registry
        config = registry.get("ai_worker")

        # Extract SSH/Docker config
        host = str(config.get("host") or "192.168.50.57")
        user = str(config.get("user") or "robotis")
        container = str(config.get("container_name") or "ai_worker_ros2")
        ros_setup = config.get("ros_setup_path")
        ros_setup_paths = [ros_setup] if ros_setup else []

        self.transport = SSHDockerTransport(
            device_id="ai_worker",
            host=host,
            user=user,
            container_name=container,
            ros_setup_paths=ros_setup_paths,
            working_directory="/root",
            timeout_s=30.0,
        )

        # Do NOT run a blocking SSH check at startup. Status stays not_checked
        # (seeded from config) until probe() runs a real connectivity test.
        self.status_store.update(
            "ai_worker",
            mode="ssh_docker",
            host=host,
            container=container,
            configured=bool(host and container),
            connection_status="not_checked",
            online=False,
        )

    async def probe(self) -> dict:
        """Run a real SSH/Docker connectivity check and update status."""
        import asyncio

        self.status_store.update("ai_worker", connection_status="checking")
        conn = await asyncio.to_thread(self.transport.check_connectivity)
        if conn.get("ok"):
            self.status_store.update("ai_worker", online=True, connection_status="online", error="", message="AI Worker SSH/Docker reachable")
        else:
            self.status_store.update(
                "ai_worker",
                online=False,
                connection_status="offline",
                error=str(conn.get("error") or "unreachable"),
                message=f"AI Worker connectivity failed: {conn.get('error')}",
            )
        return conn

    async def run_command(self, command: CommandDefinition) -> ActionResult:
        """Execute command on AI Worker via SSH Docker."""
        # Check if command is allowlisted
        configured_cmd = self.registry.command_for("ai_worker", command.command_key)
        if not configured_cmd:
            return ActionResult(
                ok=False,
                kind="command",
                name=command.name,
                error="command_not_allowlisted",
                message=f"AI Worker:{command.command_key} is not in the allowlist.",
            )

        cmd_string = str(configured_cmd)
        self.status_store.update("ai_worker", active_action=command.name, message=f"AI Worker SSH: {command.command_key}")

        try:
            result = await self.transport.async_run_command(cmd_string, run_mode="detached")
            if result.ok:
                self.status_store.update("ai_worker", active_action=None, message=f"AI Worker command started: {command.command_key}")
            else:
                self.status_store.update("ai_worker", error=result.message, message=f"AI Worker command failed: {result.message}")
            return result
        except Exception as e:
            error_msg = f"AI Worker SSH error: {str(e)}"
            self.status_store.update("ai_worker", active_action=None, error=error_msg, message=error_msg)
            return ActionResult(
                ok=False,
                kind="command",
                name=command.name,
                error="ssh_execution_error",
                message=error_msg,
            )

    async def stop(self) -> ActionResult:
        """Stop AI Worker via stop command."""
        configured_cmd = self.registry.command_for("ai_worker", "stop")
        if not configured_cmd:
            return ActionResult(
                ok=False,
                error="stop_command_not_configured",
                message="AI Worker stop command is not in the allowlist.",
            )

        self.status_store.update("ai_worker", active_action=None, message="AI Worker stop requested")
        result = await self.transport.async_run_command(str(configured_cmd), run_mode="foreground")
        return result

    async def torque_off(self) -> ActionResult:
        """Turn off AI Worker robot torque via ROS 2 service or command."""
        configured_cmd = self.registry.command_for("ai_worker", "torque_off")
        if not configured_cmd:
            return ActionResult(
                ok=False,
                error="torque_off_not_configured",
                message="AI Worker torque_off command is not configured",
            )

        self.status_store.update("ai_worker", active_action=None, message="AI Worker torque_off requested")
        result = await self.transport.async_run_command(str(configured_cmd), run_mode="foreground")
        return result

    async def kill_processes(self) -> ActionResult:
        """Force kill AI Worker robot processes."""
        configured_cmd = self.registry.command_for("ai_worker", "stop")
        if not configured_cmd:
            return ActionResult(
                ok=False,
                error="kill_command_not_configured",
                message="AI Worker kill command is not configured",
            )

        self.status_store.update("ai_worker", active_action=None, message="AI Worker kill requested")
        result = await self.transport.async_run_command(str(configured_cmd), run_mode="foreground")
        return result
