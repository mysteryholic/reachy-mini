from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "src/reachy_robotis/robotis_interface/web/routes.py"
PANEL_JS = ROOT / "src/reachy_robotis/robotis_interface/web/static/robotis_panel.js"


def main() -> None:
    html_source = ROUTES.read_text()
    js_source = PANEL_JS.read_text()

    button_ids = sorted(set(re.findall(r"<button[^>]+id=\"([^\"]+)\"", html_source)))
    missing = [button_id for button_id in button_ids if f'target.id === "{button_id}"' not in js_source]
    if missing:
        raise SystemExit(f"Buttons missing JS handlers: {', '.join(missing)}")

    for action in [
        "save",
        "test",
        "run",
        "stop",
        "save-advanced",
        "new-workflow",
        "add-existing-terminal",
        "add-custom-terminal",
        "delete-terminal",
    ]:
        if f'action === "{action}"' not in js_source:
            raise SystemExit(f"Missing product action handler for {action}")

    if "robotis_panel.js?v=20260624-presets" not in html_source:
        raise SystemExit("robotis_panel.js cache-busting query is missing")

    if "window.addEventListener(\"unhandledrejection\"" not in js_source:
        raise SystemExit("Unhandled button errors are not surfaced in the UI")

    print(f"ok: {len(button_ids)} panel buttons have JS handlers")


if __name__ == "__main__":
    main()
