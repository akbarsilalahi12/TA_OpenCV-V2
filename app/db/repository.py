"""
Repository: fungsi CRUD high-level untuk semua entity.
Dipakai oleh services dan API.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Sequence

from sqlalchemy import desc, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.db.models import (
    OccupancyLog,
    OccupancySummary,
    Slot,
    SlotStatus,
    SystemEvent,
)


# =========================
# SLOT CRUD
# =========================

def list_slots(session: Session, active_only: bool = True) -> List[Slot]:
    stmt = select(Slot)
    if active_only:
        stmt = stmt.where(Slot.is_active == 1)
    stmt = stmt.order_by(Slot.slot_code)
    return list(session.scalars(stmt).all())


def get_slot(session: Session, slot_id: int) -> Optional[Slot]:
    return session.get(Slot, slot_id)


def get_slot_by_code(session: Session, slot_code: str) -> Optional[Slot]:
    stmt = select(Slot).where(Slot.slot_code == slot_code)
    return session.scalars(stmt).first()


def create_slot(session: Session, slot_code: str, polygon: Sequence[Sequence[int]]) -> Slot:
    slot = Slot(
        slot_code=slot_code,
        polygon_json=list(polygon),
        is_active=1,
    )
    session.add(slot)
    session.flush()
    return slot


def update_slot(
    session: Session,
    slot_id: int,
    *,
    slot_code: Optional[str] = None,
    polygon: Optional[Sequence[Sequence[int]]] = None,
    is_active: Optional[bool] = None,
) -> Optional[Slot]:
    slot = session.get(Slot, slot_id)
    if slot is None:
        return None
    if slot_code is not None:
        slot.slot_code = slot_code
    if polygon is not None:
        slot.polygon_json = list(polygon)
    if is_active is not None:
        slot.is_active = 1 if is_active else 0
    session.flush()
    return slot


def soft_delete_slot(session: Session, slot_id: int) -> bool:
    slot = session.get(Slot, slot_id)
    if slot is None:
        return False
    slot.is_active = 0
    session.flush()
    return True


def hard_delete_slot(session: Session, slot_id: int) -> bool:
    slot = session.get(Slot, slot_id)
    if slot is None:
        return False
    session.delete(slot)
    session.flush()
    return True


def auto_next_slot_code(session: Session, prefix: str = "S") -> str:
    """
    Generate slot_code berikutnya, format S001, S002, ...
    """
    stmt = select(Slot.slot_code).order_by(desc(Slot.id)).limit(1)
    last = session.scalars(stmt).first()
    if last and last.startswith(prefix):
        try:
            n = int(last[len(prefix):]) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    return f"{prefix}{n:03d}"


# =========================
# STATUS / LOG
# =========================

def upsert_status(
    session: Session,
    slot_id: int,
    status: str,
    ratio: float,
) -> bool:
    """
    Upsert slot_status. Return True jika status berubah dari sebelumnya
    (caller bisa pakai info ini untuk insert log + broadcast WS).
    """
    existing = session.get(SlotStatus, slot_id)
    changed = existing is None or existing.status != status

    stmt = mysql_insert(SlotStatus).values(
        slot_id=slot_id,
        status=status,
        ratio=ratio,
    )
    stmt = stmt.on_duplicate_key_update(
        status=stmt.inserted.status,
        ratio=stmt.inserted.ratio,
    )
    session.execute(stmt)
    return changed


def insert_log(session: Session, slot_id: int, status: str, ratio: float) -> OccupancyLog:
    log = OccupancyLog(slot_id=slot_id, status=status, ratio=ratio)
    session.add(log)
    session.flush()
    return log


def insert_summary(
    session: Session,
    snapshot_at: datetime,
    total: int,
    free: int,
    full: int,
) -> OccupancySummary:
    s = OccupancySummary(
        snapshot_at=snapshot_at,
        total_slot=total,
        free_slot=free,
        full_slot=full,
    )
    session.add(s)
    session.flush()
    return s


def insert_event(session: Session, event_type: str, message: str = "") -> SystemEvent:
    ev = SystemEvent(event_type=event_type, message=message)
    session.add(ev)
    session.flush()
    return ev


# =========================
# QUERY HELPERS
# =========================

def get_status_summary(session: Session) -> dict:
    """
    Hitung total/free/full saat ini dari slot_status (untuk slot aktif).
    """
    slots = list_slots(session, active_only=True)
    total = len(slots)
    free = 0
    full = 0
    for s in slots:
        if s.status is not None:
            if s.status.status == "FREE":
                free += 1
            elif s.status.status == "FULL":
                full += 1
    return {"total": total, "free": free, "full": full}


def list_history(
    session: Session,
    *,
    slot_id: Optional[int] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[OccupancyLog]:
    if since is None:
        since = datetime.utcnow() - timedelta(hours=24)
    if until is None:
        until = datetime.utcnow()

    stmt = select(OccupancyLog).where(
        OccupancyLog.detected_at >= since,
        OccupancyLog.detected_at <= until,
    )
    if slot_id is not None:
        stmt = stmt.where(OccupancyLog.slot_id == slot_id)
    stmt = stmt.order_by(desc(OccupancyLog.detected_at)).limit(limit).offset(offset)

    return list(session.scalars(stmt).all())


def list_summary(
    session: Session,
    since: datetime,
    until: datetime,
) -> List[OccupancySummary]:
    stmt = (
        select(OccupancySummary)
        .where(OccupancySummary.snapshot_at >= since)
        .where(OccupancySummary.snapshot_at <= until)
        .order_by(OccupancySummary.snapshot_at)
    )
    return list(session.scalars(stmt).all())
