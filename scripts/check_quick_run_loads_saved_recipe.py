from __future__ import annotations

import os

import _bootstrap  # noqa: F401

os.environ["ROBOTIS_CLI_DRY_RUN"] = "1"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from reachy_robotis.robotis_interface.web.routes import mount_robotis_routes


app = FastAPI()
mount_robotis_routes(app)
client = TestClient(app)

recipe_id = "quick_run_saved_recipe_check"
recipe = {
    "recipe_id": recipe_id,
    "display_name": "Quick Run Saved Recipe Check",
    "device": "omx",
    "description": "Temporary recipe used to verify Quick Run reloads saved recipes.",
    "triggers": ["start quick run saved recipe check"],
    "terminals": [
        {
            "terminal_id": "status_topics",
            "display_name": "Status Topics",
            "connection_id": "omx_pc",
            "command_type": "container",
            "command": "ros2 topic list | head -80",
            "run_mode": "foreground",
            "start_order": 1,
            "wait_after_start_sec": 0,
            "stop_command": "true",
            "required": True,
        }
    ],
}

try:
    saved = client.post(f"/robotis/recipes/{recipe_id}", json={"recipe": recipe}).json()
    assert saved["ok"], saved
    summary = client.get("/robotis/ui/summary").json()
    assert summary["ok"], summary
    recipe_ids = [item["recipe_id"] for item in summary["recipes"]]
    assert recipe_id in recipe_ids, recipe_ids
finally:
    client.delete(f"/robotis/recipes/{recipe_id}")

print("ok quick run loads saved recipe")
