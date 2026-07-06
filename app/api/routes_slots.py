"""
Routes /api/slots — CRUD slot.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas import SlotIn, SlotListOut, SlotOut, SlotUpdate
from app.db import repository as repo
from app.db.connection import get_session
from app.db.models import Slot


router = APIRouter(prefix="/api/slots", tags=["slots"])


def _to_out(slot: Slot) -> SlotOut:
    status = slot.status.status if slot.status is not None else None
    ratio = float(slot.status.ratio) if (slot.status and slot.status.ratio is not None) else None
    return SlotOut(
        id=slot.id,
        slot_code=slot.slot_code,
        polygon=list(slot.polygon_json),
        is_active=bool(slot.is_active),
        status=status,
        ratio=ratio,
        created_at=slot.created_at,
        updated_at=slot.updated_at,
    )


@router.get("", response_model=SlotListOut)
def list_slots_endpoint(
    active_only: bool = Query(True),
    session: Session = Depends(get_session),
):
    slots: List[Slot] = repo.list_slots(session, active_only=active_only)
    items = [_to_out(s) for s in slots]
    return SlotListOut(data=items, total=len(items))


@router.get("/overrides", status_code=200)
def list_manual_overrides(
    request: Request,
):
    loop = request.app.state.detection_loop
    return {"data": loop.get_manual_overrides()}


@router.get("/{slot_id}", response_model=SlotOut)
def get_slot_endpoint(slot_id: int, session: Session = Depends(get_session)):
    slot = repo.get_slot(session, slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    return _to_out(slot)


@router.post("", response_model=SlotOut, status_code=201)
def create_slot_endpoint(payload: SlotIn, session: Session = Depends(get_session)):
    code = payload.slot_code or repo.auto_next_slot_code(session)
    if repo.get_slot_by_code(session, code) is not None:
        raise HTTPException(status_code=400, detail=f"slot_code '{code}' already exists")
    try:
        slot = repo.create_slot(session, code, payload.polygon)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e.orig)) from e
    return _to_out(slot)


@router.put("/{slot_id}", response_model=SlotOut)
def update_slot_endpoint(
    slot_id: int,
    payload: SlotUpdate,
    session: Session = Depends(get_session),
):
    if payload.slot_code:
        existing = repo.get_slot_by_code(session, payload.slot_code)
        if existing is not None and existing.id != slot_id:
            raise HTTPException(
                status_code=400,
                detail=f"slot_code '{payload.slot_code}' already used by another slot",
            )
    slot = repo.update_slot(
        session,
        slot_id,
        slot_code=payload.slot_code,
        polygon=payload.polygon,
        is_active=payload.is_active,
    )
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    session.commit()
    return _to_out(slot)


@router.delete("/{slot_id}", status_code=204)
def delete_slot_endpoint(
    slot_id: int,
    hard: bool = Query(False, description="Hard delete (hapus permanen)"),
    session: Session = Depends(get_session),
):
    ok = repo.hard_delete_slot(session, slot_id) if hard else repo.soft_delete_slot(session, slot_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Slot not found")
    session.commit()
    return None


class ManualOverrideIn(BaseModel):
    status: str  # "FREE" | "FULL"


@router.post("/{slot_id}/override", status_code=200)
def set_manual_override(
    slot_id: int,
    payload: ManualOverrideIn,
    request: Request,
    session: Session = Depends(get_session),
):
    if payload.status not in ("FREE", "FULL"):
        raise HTTPException(status_code=400, detail="status must be FREE or FULL")
    slot = repo.get_slot(session, slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    loop = request.app.state.detection_loop
    loop.set_manual_override(slot_id, payload.status)
    return {"slot_id": slot_id, "manual_status": payload.status}


@router.delete("/{slot_id}/override", status_code=200)
def clear_manual_override(
    slot_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    loop = request.app.state.detection_loop
    loop.clear_manual_override(slot_id)
    return {"slot_id": slot_id, "manual_status": None}



