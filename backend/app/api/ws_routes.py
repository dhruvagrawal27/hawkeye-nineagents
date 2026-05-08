"""WebSocket route — single endpoint for live alerts + stats ticks."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws.manager import ws_manager

router = APIRouter()


@router.websocket("/alerts")
async def ws_alerts(ws: WebSocket) -> None:
    """Token check is intentionally permissive in PREFLIGHT_MODE.

    For production, the frontend connects with `?token=<jwt>` and we'd
    validate here. For the demo we accept any client and broadcast to all.
    """
    await ws_manager.connect(ws)
    try:
        while True:
            # We don't expect inbound messages; consume to detect close
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(ws)
