"""SQLAlchemy ORM model for dataset quality results."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QualityResult(Base):
    """Stores detailed data quality results for a dataset.

    This includes a composite quality score, missing value report, duplicates
    analysis, outlier detection, skewness indicators, and actionable
    recommendations for preprocessing.
    """

    __tablename__ = "quality_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    missing_value_report: Mapped[dict] = mapped_column(JSON, nullable=False)
    duplicate_report: Mapped[dict] = mapped_column(JSON, nullable=False)
    outlier_report: Mapped[dict] = mapped_column(JSON, nullable=False)
    correlation_report: Mapped[dict] = mapped_column(JSON, nullable=False)
    skewness_report: Mapped[dict] = mapped_column(JSON, nullable=False)
    imbalance_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommendations: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    dataset: Mapped["Dataset"] = relationship(
        "Dataset", back_populates="quality_result"
    )

    def __repr__(self) -> str:
        return f"<QualityResult for dataset={self.dataset_id} score={self.quality_score}>"
