from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
routes = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()
main_html = routes.split('return """', 1)[1].split('"""', 1)[0]

for marker in ("recipe-terminal-table", "<table", "command_type", "stop_command", "ros_setup"):
    assert marker not in main_html, marker

print("ok no raw terminal table on main UI")
