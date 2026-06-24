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
    "1. Conversation Control",
    "2. SSH Delivery Setup",
    "3. Command Recipe",
    "4. Terminal Sessions / Logs",
    "5. OMX Manual Task",
    "6. OMX Hand Teleop",
    "7. Camera Visualization",
):
    assert label in html, label

for clutter in ("<nav", "Action Catalog", "Intent Resolver Test", "Execution Timeline", "Extension Guide", "Settings"):
    assert clutter not in html, clutter

js = (client.get("/robotis/static/robotis_panel.js").text)
for label in (
    "resolveConversation",
    "conversation-log",
    "runRecipe",
    "stopRecipe",
    "session_id",
    "Recipe",
    "Terminal",
    "state",
    "connectionPayload",
    "recipePayload",
    "Load existing task",
    "Save",
    "Save Recipe",
    "Test SSH",
    "Test Container",
    "Test ROS",
    "startTeleop",
    "stopTeleop",
):
    assert label in html or label in js, label

for hook in ("loadRecipe", "connectionPayload", "loadTask"):
    assert hook in js, hook

print("ok simplified gui sections")
