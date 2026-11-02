"""SQLAlchemy ORM model for engineered feature sets."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, Integer, String, Uuid
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FeatureSet(Base):
    """Represents a feature-engineered version of a dataset.

    Logs what features were engineered (using PCA, interactions, date splits, text indicators),
    how many columns were generated, and a link to the final output file.
    """

    __tablename__ = "feature_sets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    features: Mapped[list] = mapped_column(JSON, nullable=False)
    output_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        # Deleting a dataset deletes its feature sets
        backref=backref("feature_sets", cascade="all, delete-orphan", passive_deletes=True),
    )

    def __repr__(self) -> str:
        return f"<FeatureSet {self.name} method={self.method} count={self.feature_count}>"
