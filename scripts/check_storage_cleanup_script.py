from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
script = ROOT / "scripts/cleanup_reachy_robotis.sh"
source = script.read_text()

assert "config" not in source
assert "src" not in source
assert "tasks" not in source
assert "--dry-run" in source
assert "--include-build" in source
assert "--pip-cache" in source

result = subprocess.run([str(script), "--dry-run"], cwd=ROOT, text=True, capture_output=True, check=False)
assert result.returncode == 0, result.stderr

print("ok storage cleanup script")
