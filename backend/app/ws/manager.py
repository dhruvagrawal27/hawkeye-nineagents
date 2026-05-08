"""WebSocket connection manager. Singleton — one per backend process."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from fastapi import WebSocket

log = structlog.get_logger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        log.info("ws.client_connected", n_connections=len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        log.info("ws.client_disconnected", n_connections=len(self._connections))

    async def broadcast(self, payload: dict[str, Any]) -> None:
        text = json.dumps(payload, default=str)
        async with self._lock:
            connections = list(self._connections)
        if not connections:
            return
        results = await asyncio.gather(
            *(self._send(ws, text) for ws in connections),
            return_exceptions=True,
        )
        # Reap dead sockets
        for ws, result in zip(connections, results, strict=False):
            if isinstance(result, Exception):
                async with self._lock:
                    self._connections.discard(ws)

    @staticmethod
    async def _send(ws: WebSocket, text: str) -> None:
        await ws.send_text(text)

    @property
    def n_connections(self) -> int:
        return len(self._connections)


ws_manager = WebSocketManager()
