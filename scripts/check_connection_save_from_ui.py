from pathlib import Path
from tempfile import TemporaryDirectory

import _bootstrap  # noqa: F401

from reachy_robotis.robotis_interface.core.connection_registry import ConnectionRegistry
from reachy_robotis.robotis_interface.core.product_presets import ProductPresetCatalog


ROOT = Path(__file__).resolve().parents[1]
routes = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()
javascript = (ROOT / "src/reachy_robotis/robotis_interface/web/static/robotis_panel.js").read_text()
registry = (ROOT / "src/reachy_robotis/robotis_interface/core/connection_registry.py").read_text()

assert "Save Connection" in javascript
assert 'action === "save"' in javascript
assert "saveProductConnection" in javascript
assert '@router.post("/products/{product_id}/connection")' in routes
assert "Host, user, and SSH key settings are saved" in javascript
assert "Passwords stay only in memory" in javascript
assert 'auth.pop("password"' in registry

with TemporaryDirectory() as directory:
    path = Path(directory) / "connections.yaml"
    connections = ConnectionRegistry(path)
    connection_id, payload = ProductPresetCatalog().connection_payload(
        "omx",
        host="192.0.2.10",
        user="robotis",
        auth={
            "method": "password",
            "password": "not-written-to-disk",
            "key_path": "",
            "password_env": "",
        },
    )
    saved = connections.save_connection(connection_id, payload)
    assert saved.host == "192.0.2.10"
    assert saved.user == "robotis"
    assert saved.password() == "not-written-to-disk"
    assert "not-written-to-disk" not in path.read_text()
    reloaded = ConnectionRegistry(path).get(connection_id)
    assert reloaded is not None and reloaded.host == "192.0.2.10"
    assert reloaded.password() == ""

print("ok connection save from UI")
