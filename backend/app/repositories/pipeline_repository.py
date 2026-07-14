"""Data access layer for PreprocessingPipeline model."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import PreprocessingPipeline


class PipelineRepository:
    """CRUD operations for preprocessing pipelines."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, pipeline_id: uuid.UUID) -> PreprocessingPipeline | None:
        """Fetch a pipeline by its unique ID."""
        stmt = select(PreprocessingPipeline).where(PreprocessingPipeline.id == pipeline_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_dataset(self, dataset_id: uuid.UUID) -> list[PreprocessingPipeline]:
        """Fetch all pipelines generated for a dataset, ordered newest first."""
        stmt = (
            select(PreprocessingPipeline)
            .where(PreprocessingPipeline.dataset_id == dataset_id)
            .order_by(PreprocessingPipeline.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_pipeline(
        self,
        dataset_id: uuid.UUID,
        name: str,
        steps: list[dict],
        config: dict,
        output_file_path: str | None = None,
        status: str = "created",
    ) -> PreprocessingPipeline:
        """Insert a new preprocessing pipeline record."""
        pipeline = PreprocessingPipeline(
            dataset_id=dataset_id,
            name=name,
            steps=steps,
            config=config,
            output_file_path=output_file_path,
            status=status,
        )
        self.db.add(pipeline)
        await self.db.flush()
        return pipeline

    async def delete_pipeline(self, pipeline_id: uuid.UUID) -> bool:
        """Delete a pipeline record. Returns True if deleted."""
        pipeline = await self.get_by_id(pipeline_id)
        if not pipeline:
            return False
        await self.db.delete(pipeline)
        await self.db.flush()
        return True
