from __future__ import annotations

import asyncio
from typing import Any


class MockTransport:
    """Tiny async mock transport used by smoke tests and demos."""

    async def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0.01)
        return {"ok": True, "echo": payload}

