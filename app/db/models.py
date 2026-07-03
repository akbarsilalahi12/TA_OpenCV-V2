"""
ORM models — sesuai dengan app/db/schema.sql.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base


class Slot(Base):
    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    polygon_json: Mapped[list] = mapped_column(JSON, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
        nullable=False,
    )

    status: Mapped[Optional["SlotStatus"]] = relationship(
        "SlotStatus",
        uselist=False,
        cascade="all, delete-orphan",
        back_populates="slot",
    )
    logs: Mapped[List["OccupancyLog"]] = relationship(
        "OccupancyLog",
        cascade="all, delete-orphan",
        back_populates="slot",
    )


class SlotStatus(Base):
    __tablename__ = "slot_status"

    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("slots.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(Enum("FREE", "FULL", name="slot_status_enum"), nullable=False)
    ratio: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
        nullable=False,
    )

    slot: Mapped[Slot] = relationship("Slot", back_populates="status")


class OccupancyLog(Base):
    __tablename__ = "occupancy_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("slots.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Enum("FREE", "FULL", name="slot_status_enum"), nullable=False)
    ratio: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    slot: Mapped[Slot] = relationship("Slot", back_populates="logs")


class OccupancySummary(Base):
    __tablename__ = "occupancy_summary"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    free_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    full_slot: Mapped[int] = mapped_column(Integer, nullable=False)


class SystemEvent(Base):
    __tablename__ = "system_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
