from __future__ import annotations

import os
import sys
import hashlib
from pathlib import Path


try:
    from dotenv import dotenv_values, find_dotenv
except ModuleNotFoundError:
    print("python-dotenv is not installed in this Python environment.")
    print("Run this with the app venv, for example: /home/pollen/reachy_mini_env/bin/python scripts/check_openai_key_source.py")
    sys.exit(1)


def fingerprint(value: str) -> str:
    if not value:
        return "-"
    return hashlib.sha256(value.encode()).hexdigest()[:10]


def describe(path: Path) -> None:
    values = dotenv_values(path) if path.exists() else {}
    key = (values.get("OPENAI_API_KEY") or "").strip()
    model = (values.get("MODEL_NAME") or "").strip()
    print(
        f"{path}: exists={path.exists()} "
        f"key_present={bool(key)} key_len={len(key)} sha10={fingerprint(key)} "
        f"model={model or '-'}"
    )


cwd_dotenv = find_dotenv(usecwd=True)
env_key = os.getenv("OPENAI_API_KEY", "").strip()

print(f"cwd={Path.cwd()}")
print(f"find_dotenv(usecwd=True)={cwd_dotenv or '-'}")
print(f"process OPENAI_API_KEY: present={bool(env_key)} key_len={len(env_key)} sha10={fingerprint(env_key)}")
for candidate in [
    Path.cwd() / ".env",
    Path(__file__).resolve().parents[1] / ".env",
    Path(__file__).resolve().parents[1] / "src" / "reachy_robotis" / ".env",
]:
    describe(candidate)
