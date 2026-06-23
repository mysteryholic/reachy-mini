from __future__ import annotations

import ast
from pathlib import Path

import _bootstrap  # noqa: F401


# The HuggingFace key download must be guarded by an explicit opt-in flag and
# must never run by default. We assert statically that the gradio_client import
# only appears inside a conditional that checks REACHY_ROBOTIS_ENABLE_HF_FALLBACK.
console_path = Path(_bootstrap.ROOT) / "src" / "reachy_robotis" / "console.py"
source = console_path.read_text(encoding="utf-8")

assert "REACHY_ROBOTIS_ENABLE_HF_FALLBACK" in source, "HF fallback flag missing"
assert "gradium_setup" in source, "expected HF fallback code present but gated"

tree = ast.parse(source)


def _contains_flag_check(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and sub.value == "REACHY_ROBOTIS_ENABLE_HF_FALLBACK":
            return True
    return False


def _is_guarded(target_lineno: int) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _contains_flag_check(node.test):
            for sub in ast.walk(node):
                if getattr(sub, "lineno", None) == target_lineno:
                    return True
    return False


hf_lines = [
    i + 1
    for i, line in enumerate(source.splitlines())
    if "gradium_setup" in line or "claim_b_key" in line
]
assert hf_lines, "could not locate HF fetch lines"
for lineno in hf_lines:
    assert _is_guarded(lineno), f"HF fetch at line {lineno} is not gated by the opt-in flag"

# CLI flag exists.
utils_src = (Path(_bootstrap.ROOT) / "src" / "reachy_robotis" / "utils.py").read_text(encoding="utf-8")
assert "--allow-hf-key-fetch" in utils_src, "CLI flag --allow-hf-key-fetch missing"

print("ok no hf key fetch by default")
