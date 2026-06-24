from __future__ import annotations

import _bootstrap  # noqa: F401

from fastapi import FastAPI
from fastapi.testclient import TestClient

from reachy_robotis.robotis_interface.web.routes import mount_robotis_routes


app = FastAPI()
mount_robotis_routes(app)
client = TestClient(app)

html = client.get("/robotis").text
for label in (
    "1. Product Launcher",
    "2. Last Result",
):
    assert label in html, label

for clutter in (
    "<nav",
    "<h2>4. Terminal Sessions / Logs</h2>",
    "<h2>5. OMX Manual Task</h2>",
    "<h2>6. OMX Hand Teleop</h2>",
    "<h2>7. Camera Visualization</h2>",
    "Action Catalog",
    "Intent Resolver Test",
    "Execution Timeline",
    "Extension Guide",
    "Settings",
):
    assert clutter not in html, clutter

js = (client.get("/robotis/static/robotis_panel.js").text)
for label in (
    "runProduct",
    "stopProduct",
    "Workflow",
    "productConnectionPayload",
    "Test Connection",
    "Run",
    "Stop",
    "Advanced",
    "Conversation triggers",
):
    assert label in html or label in js, label

for hook in ("renderProductCards", "productConnectionPayload", "renderLastResult"):
    assert hook in js, hook

print("ok simplified gui sections")
