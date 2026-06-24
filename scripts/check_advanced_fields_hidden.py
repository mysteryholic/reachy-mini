from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
routes = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()
javascript = (ROOT / "src/reachy_robotis/robotis_interface/web/static/robotis_panel.js").read_text()

main_html = routes.split('return """', 1)[1].split('"""', 1)[0]
for hidden_field in ("ROS setup", "Container mode", "Working directory", "Stop command", "Terminal count"):
    assert hidden_field not in main_html, hidden_field

assert "<summary>Advanced</summary>" in javascript
assert "data-advanced-terminals" in javascript

print("ok advanced fields hidden")
