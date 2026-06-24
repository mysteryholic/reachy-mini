from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
routes = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()
javascript = (ROOT / "src/reachy_robotis/robotis_interface/web/static/robotis_panel.js").read_text()

assert "Reachy Mini Robot Launcher" in routes
assert '<div id="product-cards" class="product-grid"></div>' in routes
for label in ("Host/IP", "User", "Password", "SSH key", "Save Connection", "Test Connection", "Workflow", "Run", "Stop"):
    assert label in javascript, label
for product in ("OMX", "OMY", "AI Worker", "HX5 Hand"):
    assert product in (ROOT / "config/robotis_product_presets.yaml").read_text(), product

print("ok simple product cards")
