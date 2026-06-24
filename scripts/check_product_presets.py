from __future__ import annotations

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog


catalog = ProductPresetCatalog()
products = catalog.list_products()

for product_id in ("omx", "omy", "ai_worker", "hx5_hand"):
    assert product_id in products, product_id
    assert products[product_id]["workflows"], product_id

assert products["omx"]["display_name"] == "OMX"
assert products["omy"]["display_name"] == "OMY"
assert products["ai_worker"]["display_name"] == "AI Worker"
assert products["hx5_hand"]["display_name"] == "HX5 Hand"

print("ok product presets")
