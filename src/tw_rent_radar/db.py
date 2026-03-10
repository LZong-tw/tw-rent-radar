"""SQLite database layer with SQLAlchemy ORM."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    create_engine as _create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# Default data directory: ~/.tw-rent-radar/
DATA_DIR = Path.home() / ".tw-rent-radar"
DEFAULT_DB_PATH = str(DATA_DIR / "radar.db")


class Base(DeclarativeBase):
    pass


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_source_source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    price: Mapped[int | None] = mapped_column(Integer)
    city: Mapped[str | None] = mapped_column(String(50))
    district: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(500))
    size: Mapped[float | None] = mapped_column(Float)
    rooms: Mapped[str | None] = mapped_column(String(50))
    type: Mapped[str | None] = mapped_column(String(50))
    floor: Mapped[str | None] = mapped_column(String(50))
    contact: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(50))
    url: Mapped[str | None] = mapped_column(String(1000))
    images: Mapped[str | None] = mapped_column(Text)  # JSON array
    description: Mapped[str | None] = mapped_column(Text)
    amenities: Mapped[str | None] = mapped_column(Text)  # JSON array
    raw_data: Mapped[str | None] = mapped_column(Text)  # JSON object
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self, fields: list[str] | None = None) -> dict:
        """Convert listing to dict, JSON-parsing images and amenities."""
        all_fields = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        # Parse JSON fields
        for key in ("images", "amenities"):
            val = all_fields.get(key)
            if val is not None:
                try:
                    all_fields[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        if fields:
            return {k: all_fields[k] for k in fields if k in all_fields}
        return all_fields


def get_engine(db_path: str | None = None):
    """Create a SQLAlchemy engine for the given SQLite database path.

    Defaults to ~/.tw-rent-radar/radar.db so the DB location is consistent
    regardless of the working directory.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _create_engine(f"sqlite:///{db_path}", echo=False)


def create_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(engine)


def upsert_listing(session: Session, **data) -> Listing:
    """Insert a new listing or update an existing one based on (source, source_id)."""
    source = data.get("source")
    source_id = data.get("source_id")

    existing = session.query(Listing).filter_by(source=source, source_id=source_id).first()

    if existing:
        for key, value in data.items():
            if key not in ("id", "created_at"):
                setattr(existing, key, value)
        existing.updated_at = datetime.now(timezone.utc)
        session.commit()
        return existing
    else:
        listing = Listing(**data)
        session.add(listing)
        session.commit()
        return listing
