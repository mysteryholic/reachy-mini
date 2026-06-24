from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
routes = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()
javascript = (ROOT / "src/reachy_robotis/robotis_interface/web/static/robotis_panel.js").read_text()

button_ids = sorted(set(re.findall(r'<button[^>]+id="([^"]+)"', routes)))
missing = [button_id for button_id in button_ids if f'target.id === "{button_id}"' not in javascript]
assert not missing, f"Buttons missing handlers: {missing}"

for action in (
    "save",
    "test",
    "run",
    "stop",
    "save-advanced",
    "new-workflow",
    "add-existing-terminal",
    "add-custom-terminal",
    "delete-terminal",
):
    assert f'action === "{action}"' in javascript, action

assert 'href="/chat">Open Chat / Voice</a>' in routes
assert 'window.addEventListener("unhandledrejection"' in javascript

print(f"ok {len(button_ids)} visible buttons have handlers")
