"""
WS Manager: track WebSocket clients, broadcast pesan JSON.

Aman dipanggil dari thread non-asyncio via `broadcast_threadsafe`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket


log = logging.getLogger(__name__)


class WSManager:
    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Disetel oleh FastAPI lifespan untuk thread-safe scheduling."""
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        log.info("WS client connected (total=%d)", len(self._clients))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        log.info("WS client disconnected (total=%d)", len(self._clients))

    async def broadcast(self, message: dict) -> None:
        text = json.dumps(message, default=str)
        async with self._lock:
            targets = list(self._clients)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    def broadcast_threadsafe(self, message: dict) -> None:
        """Bisa dipanggil dari worker thread (detection loop)."""
        if self._loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)
        except RuntimeError:  # loop sudah ditutup
            pass


# Singleton
ws_manager = WSManager()
