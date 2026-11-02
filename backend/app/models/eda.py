"""SQLAlchemy ORM model for Exploratory Data Analysis (EDA) results."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EdaResult(Base):
    """Stores auto-generated and calculated EDA chart datasets and insights.

    Holds pre-calculated statistical coordinate arrays (e.g. histograms, heatmaps)
    so they can be rendered dynamically on the frontend.
    """

    __tablename__ = "eda_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chart_type: Mapped[str] = mapped_column(String(50), nullable=False)
    chart_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    chart_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        # Deleting a dataset deletes its EDA charts
        backref=backref("eda_results", cascade="all, delete-orphan", passive_deletes=True),
    )

    def __repr__(self) -> str:
        return f"<EdaResult {self.chart_type} for dataset={self.dataset_id}>"
