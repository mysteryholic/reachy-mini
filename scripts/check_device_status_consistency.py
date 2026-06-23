from __future__ import annotations

import _bootstrap  # noqa: F401

from fastapi import FastAPI
from fastapi.testclient import TestClient

from reachy_robotis.robotis_interface.web.routes import mount_robotis_routes


app = FastAPI()
mount_robotis_routes(app)
client = TestClient(app)

body = client.get("/robotis/status").json()
assert body.get("ok") is True, body

snapshot = body["devices"]
details = {d["id"]: d for d in body["device_details"]}

for device in ("omx", "omy", "ai_worker", "mock", "reachy"):
    snap = snapshot.get(device, {})
    det = details.get(device, {})
    assert snap.get("mode") == det.get("mode"), (
        device,
        snap.get("mode"),
        det.get("mode"),
    )

# ssh_docker devices must not claim online without a real check.
for device in ("omy", "ai_worker"):
    snap = snapshot[device]
    assert snap["mode"] == "ssh_docker", snap
    assert snap["online"] is False, snap
    assert snap["connection_status"] == "not_checked", snap
    assert snap["host"], snap
    assert snap["container"], snap

print("ok device status consistency")
