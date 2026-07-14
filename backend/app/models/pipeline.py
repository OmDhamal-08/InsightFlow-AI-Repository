"""SQLAlchemy ORM model for preprocessing pipelines."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PreprocessingPipeline(Base):
    """Represents a saved data preprocessing pipeline.

    Stores the ordered steps, specific fitted parameters (config),
    and a reference to the output cleaned dataset file.
    """

    __tablename__ = "preprocessing_pipelines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    steps: Mapped[list] = mapped_column(JSON, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    dataset: Mapped["Dataset"] = relationship(
        "Dataset", backref="preprocessing_pipelines"
    )

    def __repr__(self) -> str:
        return f"<PreprocessingPipeline {self.name} for dataset={self.dataset_id} status={self.status}>"
