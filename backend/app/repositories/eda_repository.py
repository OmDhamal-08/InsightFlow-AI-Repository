"""Data access layer for EdaResult model."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eda import EdaResult


class EdaRepository:
    """CRUD operations for Exploratory Data Analysis (EDA) results."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, eda_id: uuid.UUID) -> EdaResult | None:
        """Fetch a specific EDA chart by its unique ID."""
        stmt = select(EdaResult).where(EdaResult.id == eda_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_dataset(self, dataset_id: uuid.UUID) -> list[EdaResult]:
        """Fetch all auto-generated EDA summary charts for a dataset."""
        stmt = select(EdaResult).where(EdaResult.dataset_id == dataset_id).order_by(EdaResult.created_at.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_dataset(self, dataset_id: uuid.UUID) -> None:
        """Delete all EDA summary results for a dataset."""
        stmt = delete(EdaResult).where(EdaResult.dataset_id == dataset_id)
        await self.db.execute(stmt)

    async def bulk_create(self, dataset_id: uuid.UUID, charts: list[dict]) -> list[EdaResult]:
        """Bulk save a list of computed charts to the database."""
        # Clean up old charts first
        await self.delete_by_dataset(dataset_id)
        
        result_objs = []
        for chart in charts:
            obj = EdaResult(
                dataset_id=dataset_id,
                chart_type=chart["chart_type"],
                chart_config=chart["chart_config"],
                chart_data=chart["chart_data"],
                insight=chart["insight"],
            )
            self.db.add(obj)
            result_objs.append(obj)
        
        await self.db.flush()
        return result_objs
