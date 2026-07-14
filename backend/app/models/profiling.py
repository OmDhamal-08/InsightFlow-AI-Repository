"""SQLAlchemy ORM model for dataset profiling results."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProfilingResult(Base):
    """Stores detailed data profiling results computed for a dataset.

    This includes column types, missing values, duplicates count,
    and descriptive statistical profiles for all columns.
    """

    __tablename__ = "profiling_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    column_types: Mapped[dict] = mapped_column(JSON, nullable=False)
    null_counts: Mapped[dict] = mapped_column(JSON, nullable=False)
    unique_counts: Mapped[dict] = mapped_column(JSON, nullable=False)
    duplicate_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    descriptive_stats: Mapped[dict] = mapped_column(JSON, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    total_columns: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    dataset: Mapped["Dataset"] = relationship(
        "Dataset", back_populates="profiling_result"
    )

    def __repr__(self) -> str:
        return f"<ProfilingResult for dataset={self.dataset_id} rows={self.total_rows}>"
