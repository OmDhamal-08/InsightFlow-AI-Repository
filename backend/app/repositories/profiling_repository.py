"""Data access layer for ProfilingResult model."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profiling import ProfilingResult


class ProfilingRepository:
    """CRUD operations for dataset profiling results."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_dataset_id(self, dataset_id: uuid.UUID) -> ProfilingResult | None:
        """Fetch the profiling result associated with a dataset."""
        stmt = select(ProfilingResult).where(ProfilingResult.dataset_id == dataset_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        dataset_id: uuid.UUID,
        column_types: dict,
        null_counts: dict,
        unique_counts: dict,
        duplicate_row_count: int,
        descriptive_stats: dict,
        total_rows: int,
        total_columns: int,
    ) -> ProfilingResult:
        """Save a new profiling result, replacing any existing one for this dataset."""
        existing = await self.get_by_dataset_id(dataset_id)
        if existing:
            existing.column_types = column_types
            existing.null_counts = null_counts
            existing.unique_counts = unique_counts
            existing.duplicate_row_count = duplicate_row_count
            existing.descriptive_stats = descriptive_stats
            existing.total_rows = total_rows
            existing.total_columns = total_columns
            await self.db.flush()
            return existing

        profile = ProfilingResult(
            dataset_id=dataset_id,
            column_types=column_types,
            null_counts=null_counts,
            unique_counts=unique_counts,
            duplicate_row_count=duplicate_row_count,
            descriptive_stats=descriptive_stats,
            total_rows=total_rows,
            total_columns=total_columns,
        )
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def delete_by_dataset_id(self, dataset_id: uuid.UUID) -> bool:
        """Delete a dataset's profiling result. Returns True if found & deleted."""
        profile = await self.get_by_dataset_id(dataset_id)
        if not profile:
            return False
        await self.db.delete(profile)
        await self.db.flush()
        return True
