from __future__ import annotations

import re

import _bootstrap  # noqa: F401

from fastapi import FastAPI
from fastapi.testclient import TestClient

from reachy_robotis.config import config
from reachy_robotis.secret_utils import mask_api_key
from reachy_robotis.robotis_interface.web.routes import mount_robotis_routes


# mask_api_key must never echo the raw secret.
sample = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890wxyz87IA"
masked = mask_api_key(sample)
assert sample not in masked, masked
assert masked.startswith("sk-proj") and masked.endswith("87IA"), masked
assert mask_api_key("") == "(missing)"
assert mask_api_key(None) == "(missing)"

app = FastAPI()
mount_robotis_routes(app)
client = TestClient(app)

key = (config.OPENAI_API_KEY or "").strip()
key_like = re.compile(r"sk-[A-Za-z0-9_-]{20,}")

for path in ("/robotis/health", "/robotis/status", "/robotis/actions", "/robotis/ui/summary"):
    body = client.get(path).text
    if key:
        assert key not in body, f"raw OPENAI_API_KEY leaked in {path}"
    assert not key_like.search(body), f"key-like string leaked in {path}"

print("ok no api key leak")
