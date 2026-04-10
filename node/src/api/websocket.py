"""WebSocket broadcaster — pushes events to all connected dashboard clients."""

import asyncio
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketBroadcaster:
    def __init__(self) -> None:
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.remove(ws)

    async def broadcast(self, event_type: str, data: dict) -> None:
        msg = json.dumps({"type": event_type, "data": data})
        dead: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.remove(ws)
