from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()

for hidden_heading in (
    "<h2>4. Terminal Sessions / Logs</h2>",
    "<h2>5. OMX Manual Task</h2>",
    "<h2>6. OMX Hand Teleop</h2>",
    "<h2>7. Camera Visualization</h2>",
):
    assert hidden_heading not in source, hidden_heading

assert "Show full logs" in source
javascript = (ROOT / "src/reachy_robotis/robotis_interface/web/static/robotis_panel.js").read_text()
assert "<summary>Advanced</summary>" in javascript

print("ok advanced sections hidden")
