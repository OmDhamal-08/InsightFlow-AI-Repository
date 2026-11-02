"""SQLAlchemy ORM models for AutoML experiments (Phase 10) and trained models (Phase 11)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Experiment(Base):
    """One AutoML run: a dataset, a target column and a set of algorithms to compare.

    ``config`` stores the user's choices (algorithms, CV folds, tuning, ...) and
    ``summary`` stores what the engine actually did (rows used, columns dropped,
    class distribution), so the run is fully reproducible and explainable.
    """

    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_column: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    optimize_metric: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | completed | failed
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    best_model_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        backref=backref("experiments", cascade="all, delete-orphan", passive_deletes=True),
    )
    models: Mapped[list["TrainedModel"]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TrainedModel.rank",
    )

    def __repr__(self) -> str:
        return f"<Experiment {self.name} target={self.target_column} status={self.status}>"


class TrainedModel(Base):
    """A single algorithm trained inside an experiment, with its scores and evaluation data."""

    __tablename__ = "trained_models"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    algorithm: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # completed | failed
    hyperparameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    cv_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cv_std: Mapped[float | None] = mapped_column(Float, nullable=True)
    test_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evaluation: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    training_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_best: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    experiment: Mapped["Experiment"] = relationship(back_populates="models")

    def __repr__(self) -> str:
        return f"<TrainedModel {self.algorithm} rank={self.rank} cv={self.cv_score}>"
