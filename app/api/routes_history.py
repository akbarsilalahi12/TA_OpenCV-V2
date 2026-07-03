"""
Routes /api/history dan /api/summary.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import HistoryItem, HistoryListOut, SummaryOut, SummaryPoint
from app.db import repository as repo
from app.db.connection import get_session


router = APIRouter(prefix="/api", tags=["history"])


@router.get("/history", response_model=HistoryListOut)
def history_endpoint(
    slot_id: Optional[int] = None,
    since: Optional[datetime] = Query(None, alias="from"),
    until: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    rows = repo.list_history(
        session,
        slot_id=slot_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    # build response (load slot_code via relationship)
    items = []
    for r in rows:
        code = r.slot.slot_code if r.slot is not None else f"#{r.slot_id}"
        items.append(
            HistoryItem(
                id=r.id,
                slot_id=r.slot_id,
                slot_code=code,
                status=r.status,
                ratio=float(r.ratio) if r.ratio is not None else None,
                detected_at=r.detected_at,
            )
        )
    return HistoryListOut(data=items, total=len(items))


_RANGE_MAP = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

_AUTO_BUCKET = {
    "1h": "minute",
    "6h": "minute",
    "24h": "hour",
    "7d": "hour",
    "30d": "day",
}


@router.get("/summary", response_model=SummaryOut)
def summary_endpoint(
    range: str = Query("24h"),
    bucket: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    if range not in _RANGE_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid range. Allowed: {list(_RANGE_MAP)}")
    if bucket is None:
        bucket = _AUTO_BUCKET[range]
    if bucket not in {"minute", "hour", "day"}:
        raise HTTPException(status_code=400, detail="bucket must be minute|hour|day")

    until = datetime.utcnow()
    since = until - _RANGE_MAP[range]
    rows = repo.list_summary(session, since=since, until=until)

    # Bucketing in Python (sederhana — data harian < 100K row, masih ringan).
    buckets: dict[datetime, list[tuple[int, int, int]]] = {}
    for r in rows:
        t = r.snapshot_at
        if bucket == "minute":
            key = t.replace(second=0, microsecond=0)
        elif bucket == "hour":
            key = t.replace(minute=0, second=0, microsecond=0)
        else:
            key = t.replace(hour=0, minute=0, second=0, microsecond=0)
        buckets.setdefault(key, []).append((r.total_slot, r.free_slot, r.full_slot))

    points = []
    for key in sorted(buckets):
        pts = buckets[key]
        n = len(pts)
        avg_total = sum(p[0] for p in pts) // n
        avg_free = sum(p[1] for p in pts) // n
        avg_full = sum(p[2] for p in pts) // n
        points.append(SummaryPoint(time=key, total=avg_total, free=avg_free, full=avg_full))

    return SummaryOut(range=range, bucket=bucket, data=points)
