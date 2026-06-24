from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
routes = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()
actions = (
    (ROOT / "config/robotis_actions.yaml").read_text()
    + (ROOT / "config/robotis_product_presets.yaml").read_text()
)

for phrase in ("start OMX", "start OMX MoveIt", "play OMX demo", "start OMY MoveIt", "stop everything"):
    assert phrase in actions, phrase

assert '@router.post("/intent/resolve")' in routes
assert '@router.post("/actions/run")' in routes
assert 'ProductPresetCatalog' in routes
assert 'Talk to Reachy' not in routes

print("ok conversation to workflow")
