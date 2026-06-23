from __future__ import annotations

import os
import time
import json
import http.client
from typing import Any


class OMXBridgeTransport:
    """HTTP transport for the existing OMX MoveL bridge."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.host = str(os.getenv("OMX_BRIDGE_HOST") or config.get("bridge_host") or config.get("host") or "").strip()
        self.port = int(os.getenv("OMX_BRIDGE_PORT") or config.get("bridge_port") or config.get("port") or 18001)
        self.timeout_s = float(config.get("bridge_timeout_s", 2.0))
        self.robot = str(config.get("robot_name") or "omx")

    @property
    def enabled(self) -> bool:
        return bool(self.host)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def get_status(self) -> dict[str, Any]:
        return self._request("GET", None, timeout=0.6)

    def wait_until_online(self, *, timeout_s: float = 12.0, interval_s: float = 0.4) -> dict[str, Any]:
        deadline = time.monotonic() + max(0.1, timeout_s)
        last: dict[str, Any] = {"ok": False, "accepted": False, "error": "not_checked", "url": self.url}
        while time.monotonic() < deadline:
            last = self.get_status()
            if bool(last.get("ok", last.get("accepted", False))):
                last.setdefault("url", self.url)
                return last
            time.sleep(max(0.05, interval_s))
        last.setdefault("url", self.url)
        last["ok"] = False
        last["accepted"] = False
        last["error"] = str(last.get("error") or "bridge_health_timeout")
        last["timeout_s"] = timeout_s
        return last

    def send_sequence(self, name: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
        return self._post(
            {
                "type": "sequence",
                "robot": self.robot,
                "source": "reachy_robotis",
                "name": name,
                "steps": steps,
                "metadata": {"app": "reachy_robotis"},
                "stamp": time.time(),
            }
        )

    def send_move_l(self, pose: dict[str, float], duration: float) -> dict[str, Any]:
        return self._post(
            {
                "type": "primitive",
                "robot": self.robot,
                "source": "reachy_robotis",
                "cmd": "move_l",
                "args": {"pose": pose, "duration": float(duration)},
                "stamp": time.time(),
            }
        )

    def send_gripper(self, command: str) -> dict[str, Any]:
        aperture = 1.0 if command == "open" else 0.0
        return self._post(
            {
                "type": "gripper",
                "robot": self.robot,
                "source": "reachy_robotis",
                "aperture": aperture,
                "stamp": time.time(),
            }
        )

    def send_absolute(self, pose: dict[str, float], aperture: float | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "absolute",
            "robot": self.robot,
            "source": "reachy_robotis",
            "x": float(pose["x"]),
            "y": float(pose["y"]),
            "z": float(pose["z"]),
            "confidence": 1.0,
            "stamp": time.time(),
        }
        if aperture is not None:
            payload["aperture"] = float(aperture)
        return self._post(payload, timeout=0.5)

    def send_enable(self, value: bool) -> dict[str, Any]:
        return self._post(
            {
                "type": "enable",
                "robot": self.robot,
                "source": "reachy_robotis",
                "value": bool(value),
                "stamp": time.time(),
            },
            timeout=0.6,
        )

    def send_stop(self) -> dict[str, Any]:
        return self._post(
            {
                "type": "stop",
                "robot": self.robot,
                "source": "reachy_robotis",
                "stamp": time.time(),
            },
            timeout=0.8,
        )

    def _post(self, payload: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        return self._request("POST", payload, timeout=timeout)

    def _request(self, method: str, payload: dict[str, Any] | None, timeout: float | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "accepted": False, "error": "OMX bridge host is not configured"}
        connection = http.client.HTTPConnection(self.host, self.port, timeout=timeout or self.timeout_s)
        try:
            if method == "GET":
                connection.request("GET", "/", headers={"Connection": "close"})
            else:
                body = json.dumps(payload).encode("utf-8")
                connection.request(
                    "POST",
                    "/",
                    body=body,
                    headers={
                        "Content-Type": "application/json",
                        "Content-Length": str(len(body)),
                        "Connection": "close",
                    },
                )
            response = connection.getresponse()
            data = response.read()
            if response.status >= 400:
                return {"ok": False, "accepted": False, "error": f"HTTP {response.status}", "status": response.status}
            if not data:
                return {"ok": True, "accepted": True}
            parsed = json.loads(data.decode("utf-8"))
            if not isinstance(parsed, dict):
                return {"ok": True, "accepted": True, "response": parsed}
            parsed.setdefault("ok", bool(parsed.get("accepted", True)))
            return parsed
        except Exception as exc:
            return {"ok": False, "accepted": False, "error": str(exc), "url": self.url}
        finally:
            connection.close()
