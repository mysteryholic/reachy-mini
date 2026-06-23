from __future__ import annotations

from typing import Any


class HTTPTransport:
    """Placeholder for future HTTP robot endpoints."""

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "error": "not_implemented", "path": path, "payload": payload}

