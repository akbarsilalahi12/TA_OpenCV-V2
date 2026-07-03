"""
FastAPI app entry point.

- Bootstrap RTSPReader + DetectionLoop pada startup
- Bind WS manager ke event loop
- Mount static frontend
- Daftarkan semua router
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import repository as repo
from app.db.connection import SessionLocal
from app.services.detection_loop import DetectionLoop
from app.services.rtsp_reader import RTSPReader
from app.services.ws_manager import ws_manager


# ===== Logging =====
log_dir = Path(settings.log_file).parent
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(settings.log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bind ws manager ke event loop yang sedang aktif.
    ws_manager.bind_loop(asyncio.get_running_loop())

    # Inisialisasi reader + detection loop.
    reader = RTSPReader(
        url=settings.rtsp_url,
        target_size=(settings.frame_width, settings.frame_height),
    )

    def _on_rtsp_event(event_type: str, message: str):
        # Tulis event sistem ke DB + broadcast ke WS.
        try:
            with SessionLocal() as s:
                repo.insert_event(s, event_type, message)
                s.commit()
        except Exception:
            log.exception("Gagal tulis system_event")
        ws_manager.broadcast_threadsafe({
            "type": "system_event",
            "data": {"event_type": event_type, "message": message},
        })

    reader.set_event_callback(_on_rtsp_event)
    reader.start()

    loop = DetectionLoop(reader)
    loop.start()

    app.state.rtsp_reader = reader
    app.state.detection_loop = loop

    # Startup event
    try:
        with SessionLocal() as s:
            repo.insert_event(s, "STARTUP", f"API v1 listening on {settings.api_host}:{settings.api_port}")
            s.commit()
    except Exception:
        log.exception("Gagal tulis STARTUP event")

    log.info("App startup complete")
    try:
        yield
    finally:
        log.info("App shutting down...")
        try:
            with SessionLocal() as s:
                repo.insert_event(s, "SHUTDOWN", "Graceful shutdown")
                s.commit()
        except Exception:
            pass
        loop.stop()
        reader.stop()
        log.info("App shutdown complete")


app = FastAPI(
    title="Sistem Deteksi Slot Parkir",
    description="Tugas Akhir — deteksi okupansi slot parkir berbasis OpenCV",
    version="1.0.0",
    lifespan=lifespan,
)


# ===== Routers =====
from app.api import routes_slots, routes_status, routes_video, routes_history, ws_slots  # noqa: E402

app.include_router(routes_status.router)
app.include_router(routes_slots.router)
app.include_router(routes_video.router)
app.include_router(routes_history.router)
app.include_router(ws_slots.router)


# ===== Static Frontend =====
WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"

if WEB_DIR.exists():
    # Serve dashboard
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(str(WEB_DIR / "index.html"))

    @app.get("/admin", include_in_schema=False)
    def admin_page():
        admin_file = WEB_DIR / "admin.html"
        if admin_file.exists():
            return FileResponse(str(admin_file))
        return FileResponse(str(WEB_DIR / "index.html"))

    # Asset lain (css/js)
    app.mount("/assets", StaticFiles(directory=str(WEB_DIR)), name="assets")
