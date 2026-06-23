from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.command_catalog import CommandCatalog


catalog = CommandCatalog()
assert catalog.get("omy_leader_follower") is not None
assert catalog.get("ai_worker_bringup") is not None
print(f"ok command catalog: {len(catalog.list_commands())} command(s)")

