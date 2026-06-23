from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.recipe_catalog import RecipeCatalog


catalog = RecipeCatalog()

for recipe in catalog.list_recipes():
    assert recipe.display_name, recipe
    assert recipe.device, recipe
    assert recipe.terminals, recipe.recipe_id
    orders = []
    for terminal in recipe.terminals:
        assert terminal.terminal_id, terminal
        assert terminal.connection_id, terminal
        assert terminal.command_type in {"host", "container"}, terminal
        assert terminal.command, terminal
        assert terminal.run_mode in {"foreground", "detached"}, terminal
        assert isinstance(terminal.start_order, int), terminal
        orders.append(terminal.start_order)
    assert orders == sorted(orders), (recipe.recipe_id, orders)

print("ok terminal plan schema")
