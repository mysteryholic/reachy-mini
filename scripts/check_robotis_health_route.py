from __future__ import annotations

import _bootstrap  # noqa: F401

from fastapi import FastAPI
from fastapi.testclient import TestClient

from reachy_robotis.robotis_interface.web.routes import mount_robotis_routes


app = FastAPI()
mount_robotis_routes(app)
client = TestClient(app)

resp = client.get("/robotis/health")
assert resp.status_code == 200, resp.status_code
body = resp.json()

assert body.get("ok") is True, body
assert body.get("app") == "reachy_robotis", body
assert body.get("robotis_status") == "running", body
assert body.get("voice_status") in {"enabled", "disabled"}, body
assert body.get("openai_key_status") in {"configured", "missing", "invalid", "unknown"}, body

devices = body.get("devices", {})
for device in ("omx", "omy", "ai_worker"):
    assert device in devices, (device, devices)

print("ok robotis health route")
