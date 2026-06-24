from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
javascript = (ROOT / "src/reachy_robotis/robotis_interface/web/static/robotis_panel.js").read_text()

for field in ('name="host"', 'name="user"', 'name="password"', 'name="key_path"', 'name="workflow"'):
    assert field in javascript, field

for forbidden in ('name="container_name"', 'name="working_dir"', 'name="ros_setup"', 'name="command_type"'):
    assert forbidden not in javascript, forbidden

assert "/products/${encodeURIComponent(productId)}/connection" in javascript

print("ok user only needs host user password or key")
