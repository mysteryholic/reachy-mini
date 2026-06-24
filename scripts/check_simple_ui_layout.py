from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "src/reachy_robotis/robotis_interface/web/routes.py").read_text()
console = (ROOT / "src/reachy_robotis/console.py").read_text()
main = (ROOT / "src/reachy_robotis/main.py").read_text()

for heading in (
    "1. Product Launcher",
    "2. Last Result",
):
    assert f"<h2>{heading}</h2>" in source, heading

for button in ("Refresh", "Stop All"):
    assert f">{button}</button>" in source, button

assert 'RedirectResponse(url="/chat")' in console
assert 'RedirectResponse(url="/chat")' in main
assert 'href="/chat">Open Chat / Voice</a>' in source
assert "Talk to Reachy" not in source

print("ok simple UI layout")
