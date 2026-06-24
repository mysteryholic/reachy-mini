from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
routes = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()
javascript = (ROOT / "src/reachy_robotis/robotis_interface/web/static/robotis_panel.js").read_text()
transport = (ROOT / "src/reachy_robotis/robotis_interface/transports/connection_transport.py").read_text()
registry = (ROOT / "src/reachy_robotis/robotis_interface/core/connection_registry.py").read_text()

assert '@router.post("/connections/{connection_id}/test")' in routes
for marker in ("test_tcp", '"ssh"', "docker inspect --", "ros2 topic list", "Connection test: OK"):
    assert marker in routes, marker

assert 'type="password"' in javascript
assert '@router.post("/products/{product_id}/test")' in routes
assert "SSH_ASKPASS" in transport
assert '"BatchMode=no"' in transport
assert '"BatchMode=yes"' in transport
assert '"password": self._password' not in registry
assert '"password"' not in registry.split("def to_public_mapping", 1)[1].split("class ConnectionRegistry", 1)[0]

print("ok connection test flow")
