"""
Endpoint WebSocket /ws/slots.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import ws_manager


log = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])


@router.websocket("/ws/slots")
async def ws_slots(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # Heartbeat task
        async def heartbeat():
            while True:
                await asyncio.sleep(30)
                try:
                    await ws.send_json({"type": "ping"})
                except Exception:
                    break

        hb = asyncio.create_task(heartbeat())
        try:
            while True:
                # Server tidak butuh data dari client; cuma jaga koneksi.
                await ws.receive_text()
        finally:
            hb.cancel()
    except WebSocketDisconnect:
        pass
    except Exception as e:  # pragma: no cover
        log.warning("WS error: %s", e)
    finally:
        await ws_manager.disconnect(ws)
