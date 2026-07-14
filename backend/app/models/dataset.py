"""SQLAlchemy ORM model for uploaded datasets."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Dataset(Base):
    """Represents an uploaded dataset file (CSV/Excel).

    Stores metadata about the file (size, hash, row/column counts)
    and a reference to the file on disk. The ``file_hash`` column
    enables SHA-256-based duplicate detection per user.
    """

    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", backref="datasets")
    profiling_result: Mapped["ProfilingResult"] = relationship(
        "ProfilingResult", back_populates="dataset", uselist=False, cascade="all, delete-orphan"
    )
    quality_result: Mapped["QualityResult"] = relationship(
        "QualityResult", back_populates="dataset", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Dataset {self.name} ({self.file_type}, {self.row_count} rows)>"
