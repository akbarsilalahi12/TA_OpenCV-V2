"""
Pydantic schemas untuk request/response API.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============= Slot =============

class SlotIn(BaseModel):
    slot_code: Optional[str] = Field(None, min_length=1, max_length=20)
    polygon: List[List[int]] = Field(..., min_length=3)


class SlotUpdate(BaseModel):
    slot_code: Optional[str] = Field(None, min_length=1, max_length=20)
    polygon: Optional[List[List[int]]] = Field(None, min_length=3)
    is_active: Optional[bool] = None


class SlotStatusOut(BaseModel):
    status: Optional[Literal["FREE", "FULL"]] = None
    ratio: Optional[float] = None
    updated_at: Optional[datetime] = None


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slot_code: str
    polygon: List[List[int]]
    is_active: bool
    status: Optional[Literal["FREE", "FULL"]] = None
    ratio: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class SlotListOut(BaseModel):
    data: List[SlotOut]
    total: int


# ============= Status / Summary =============

class StatusSummaryOut(BaseModel):
    total_slot: int
    free_slot: int
    full_slot: int
    occupancy_rate: float
    as_of: datetime


# ============= History =============

class HistoryItem(BaseModel):
    id: int
    slot_id: int
    slot_code: str
    status: Literal["FREE", "FULL"]
    ratio: Optional[float] = None
    detected_at: datetime


class HistoryListOut(BaseModel):
    data: List[HistoryItem]
    total: int


# ============= Summary chart =============

class SummaryPoint(BaseModel):
    time: datetime
    free: int
    full: int
    total: int


class SummaryOut(BaseModel):
    range: str
    bucket: str
    data: List[SummaryPoint]


# ============= Health =============

class HealthOut(BaseModel):
    status: str = "ok"
    rtsp_connected: bool
    db_connected: bool
    fps: float
    uptime_seconds: int
