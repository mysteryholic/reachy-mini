from __future__ import annotations

from typing import Any

from fastapi import WebSocket


class WebSocketTransport:
    """Small helper around FastAPI WebSocket JSON messages."""

    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket

    async def receive_json(self) -> dict[str, Any]:
        payload = await self.websocket.receive_json()
        return dict(payload)

    async def send_json(self, payload: dict[str, Any]) -> None:
        await self.websocket.send_json(payload)

