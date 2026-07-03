"""
Entry point: jalankan detection engine SAJA (tanpa API + tanpa GUI).
Berguna untuk debug pipeline & memastikan data masuk ke MySQL.

    python run_engine.py
"""

from __future__ import annotations

import logging
import signal
import time

from app.config import settings
from app.db import repository as repo
from app.db.connection import SessionLocal
from app.services.detection_loop import DetectionLoop
from app.services.rtsp_reader import RTSPReader


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log = logging.getLogger("engine")

    reader = RTSPReader(
        url=settings.rtsp_url,
        target_size=(settings.frame_width, settings.frame_height),
    )

    def on_event(event_type: str, message: str) -> None:
        try:
            with SessionLocal() as s:
                repo.insert_event(s, event_type, message)
                s.commit()
        except Exception:
            log.exception("Gagal tulis event")

    reader.set_event_callback(on_event)
    reader.start()

    loop = DetectionLoop(reader)
    loop.start()

    log.info("Engine running. Tekan Ctrl+C untuk berhenti.")

    stopped = {"v": False}

    def _stop(*_):
        stopped["v"] = True

    signal.signal(signal.SIGINT, _stop)
    try:
        signal.signal(signal.SIGTERM, _stop)
    except Exception:
        pass

    try:
        while not stopped["v"]:
            time.sleep(1)
    finally:
        loop.stop()
        reader.stop()
        log.info("Engine stop")


if __name__ == "__main__":
    main()
