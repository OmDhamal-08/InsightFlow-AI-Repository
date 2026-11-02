"""Data access layer for Experiment and TrainedModel models."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.experiment import Experiment, TrainedModel


class ExperimentRepository:
    """CRUD operations for AutoML experiments and their trained models."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, experiment_id: uuid.UUID, user_id: uuid.UUID) -> Experiment | None:
        """Fetch an experiment owned by the user, with models and dataset eagerly loaded."""
        stmt = (
            select(Experiment)
            .options(selectinload(Experiment.models), selectinload(Experiment.dataset))
            .where(Experiment.id == experiment_id, Experiment.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID, dataset_id: uuid.UUID | None = None) -> list[Experiment]:
        """All experiments for the user (optionally one dataset), newest first."""
        stmt = (
            select(Experiment)
            .options(selectinload(Experiment.models), selectinload(Experiment.dataset))
            .where(Experiment.user_id == user_id)
            .order_by(Experiment.created_at.desc())
        )
        if dataset_id:
            stmt = stmt.where(Experiment.dataset_id == dataset_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_ids_for_dataset(self, dataset_id: uuid.UUID) -> list[uuid.UUID]:
        """IDs of experiments on a dataset (used to clean up model files)."""
        result = await self.db.execute(select(Experiment.id).where(Experiment.dataset_id == dataset_id))
        return list(result.scalars().all())

    async def create(self, **fields) -> Experiment:
        experiment = Experiment(**fields)
        self.db.add(experiment)
        await self.db.flush()
        return experiment

    async def add_model(self, **fields) -> TrainedModel:
        model = TrainedModel(**fields)
        self.db.add(model)
        await self.db.flush()
        return model

    async def get_model(self, experiment_id: uuid.UUID, model_id: uuid.UUID) -> TrainedModel | None:
        stmt = select(TrainedModel).where(
            TrainedModel.id == model_id, TrainedModel.experiment_id == experiment_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, experiment: Experiment) -> None:
        await self.db.delete(experiment)
        await self.db.flush()

    async def count_experiments(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(select(func.count(Experiment.id)).where(Experiment.user_id == user_id))
        return int(result.scalar() or 0)

    async def count_trained_models(self, user_id: uuid.UUID) -> int:
        """Number of successfully trained models across the user's experiments."""
        stmt = (
            select(func.count(TrainedModel.id))
            .join(Experiment, TrainedModel.experiment_id == Experiment.id)
            .where(Experiment.user_id == user_id, TrainedModel.status == "completed")
        )
        result = await self.db.execute(stmt)
        return int(result.scalar() or 0)
