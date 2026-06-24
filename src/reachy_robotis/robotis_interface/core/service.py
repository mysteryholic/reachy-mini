from __future__ import annotations

from reachy_robotis.robotis_interface.adapters.omy_adapter import OMYAdapter
from reachy_robotis.robotis_interface.adapters.omx_adapter import OMXAdapter
from reachy_robotis.robotis_interface.core.task_catalog import TaskCatalog
from reachy_robotis.robotis_interface.adapters.mock_adapter import MockAdapter
from reachy_robotis.robotis_interface.core.status_store import StatusStore
from reachy_robotis.robotis_interface.core.action_catalog import ActionCatalog
from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog
from reachy_robotis.robotis_interface.core.device_registry import DeviceRegistry
from reachy_robotis.robotis_interface.core.action_executor import ActionExecutor
from reachy_robotis.robotis_interface.adapters.reachy_adapter import ReachyAdapter
from reachy_robotis.robotis_interface.core.command_catalog import CommandCatalog
from reachy_robotis.robotis_interface.adapters.ai_worker_adapter import AIWorkerAdapter
from reachy_robotis.robotis_interface.core.intent_resolver import IntentResolver
from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog
from reachy_robotis.robotis_interface.transports.cli_transport import CLITransport
from reachy_robotis.robotis_interface.core.terminal_session_manager import TerminalSessionManager


_EXECUTOR: ActionExecutor | None = None

# Modes that are available immediately without a remote check.
_LOCAL_MODES = {"mock", "conversation"}


def _seed_device_status(status_store: StatusStore, device: str, config: dict) -> None:
    """Seed authoritative, config-derived status for one device.

    Remote devices (ssh_docker/ssh/bridge) start ``online=False`` with
    ``connection_status="not_checked"`` because no real connectivity test has
    run yet. Local modes (mock/conversation) are considered online.
    """
    mode = str(config.get("mode") or "mock")
    enabled = bool(config.get("enabled", True))
    host = str(config.get("host") or config.get("bridge_host") or "")
    container = str(config.get("container_name") or "")

    if mode in _LOCAL_MODES:
        online = enabled
        connection_status = "online" if enabled else "offline"
        configured = True
    else:
        # Remote transports require a real check before claiming online.
        online = False
        connection_status = "not_checked"
        if mode == "bridge":
            configured = bool(host)
        elif mode in {"ssh_docker"}:
            configured = bool(host and container)
        else:
            configured = bool(host)

    status_store.seed_device(
        device,
        mode=mode,
        configured=configured,
        online=online,
        connection_status=connection_status,
        host=host,
        container=container,
    )


def get_robotis_executor() -> ActionExecutor:
    """Return the process-wide ROBOTIS interface executor."""
    global _EXECUTOR
    if _EXECUTOR is not None:
        return _EXECUTOR

    status_store = StatusStore()
    registry = DeviceRegistry()
    connection_registry = ConnectionRegistry()
    task_catalog = TaskCatalog()
    command_catalog = CommandCatalog()
    action_catalog = ActionCatalog()
    recipe_catalog = RecipeCatalog()
    product_presets = ProductPresetCatalog()
    product_presets.install(connection_registry, recipe_catalog, action_catalog)
    terminal_session_manager = TerminalSessionManager(recipe_catalog, connection_registry)
    resolver = IntentResolver(task_catalog, command_catalog, action_catalog, recipe_catalog)

    # Seed device status from config FIRST so config is the single source of
    # truth. Adapters created afterwards only refine online/connection_status
    # via real checks; they never invent a different mode/host than config.
    for device, config in registry.list_devices().items():
        _seed_device_status(status_store, device, config)

    adapters = {
        "reachy": ReachyAdapter(status_store=status_store),
        "omx": OMXAdapter(status_store=status_store, registry=registry),
        "omy": OMYAdapter(status_store=status_store, registry=registry),
        "ai_worker": AIWorkerAdapter(status_store=status_store, registry=registry),
        "mock": MockAdapter(status_store=status_store),
    }

    _EXECUTOR = ActionExecutor(
        task_catalog=task_catalog,
        command_catalog=command_catalog,
        resolver=resolver,
        adapters=adapters,
        status_store=status_store,
        registry=registry,
        connection_registry=connection_registry,
        action_catalog=action_catalog,
        recipe_catalog=recipe_catalog,
        terminal_session_manager=terminal_session_manager,
    )
    return _EXECUTOR
