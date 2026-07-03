"""
Routes /api/status dan /health.
"""

from __future__ import annotations

import time
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import HealthOut, StatusSummaryOut
from app.db import repository as repo
from app.db.connection import get_session


router = APIRouter(tags=["status"])

_started_at = time.time()


@router.get("/api/status", response_model=StatusSummaryOut)
def status_summary(session: Session = Depends(get_session)):
    s = repo.get_status_summary(session)
    total = s["total"]
    occ = (s["full"] / total) if total else 0.0
    return StatusSummaryOut(
        total_slot=total,
        free_slot=s["free"],
        full_slot=s["full"],
        occupancy_rate=round(occ, 3),
        as_of=datetime.utcnow(),
    )


@router.get("/health", response_model=HealthOut)
def health(request: Request, session: Session = Depends(get_session)):
    # DB ping
    try:
        session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    reader = getattr(request.app.state, "rtsp_reader", None)
    loop = getattr(request.app.state, "detection_loop", None)

    return HealthOut(
        status="ok" if db_ok else "degraded",
        rtsp_connected=bool(reader and reader.is_connected()),
        db_connected=db_ok,
        fps=loop.get_fps() if loop else 0.0,
        uptime_seconds=int(time.time() - _started_at),
    )
