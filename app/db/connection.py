"""
Koneksi MySQL via SQLAlchemy 2.x.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base class untuk semua ORM model."""


# Engine dengan connection pool. pool_recycle 1 jam untuk hindari MySQL "wait_timeout".
engine = create_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    """Dependency injection untuk FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
