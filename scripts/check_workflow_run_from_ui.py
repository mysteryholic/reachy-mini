from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
routes = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()
javascript = (ROOT / "src/reachy_robotis/robotis_interface/web/static/robotis_panel.js").read_text()

for marker in ("Workflow", "Run", "Stop", "Test Connection"):
    assert marker in javascript, marker

assert '@router.post("/recipes/{recipe_id}/run")' in routes
assert '@router.post("/recipes/{recipe_id}/stop")' in routes
assert 'action === "run"' in javascript
assert 'action === "stop"' in javascript
assert "runProduct" in javascript
assert "stopProduct" in javascript

print("ok workflow run from UI")
