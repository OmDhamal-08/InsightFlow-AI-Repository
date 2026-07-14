"""Data access layer for FeatureSet model."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feature import FeatureSet


class FeatureRepository:
    """CRUD operations for engineered feature sets."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, feature_set_id: uuid.UUID) -> FeatureSet | None:
        """Fetch a specific FeatureSet by its unique ID."""
        stmt = select(FeatureSet).where(FeatureSet.id == feature_set_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_dataset(self, dataset_id: uuid.UUID) -> list[FeatureSet]:
        """Fetch all feature sets created for a dataset, ordered newest first."""
        stmt = select(FeatureSet).where(FeatureSet.dataset_id == dataset_id).order_by(FeatureSet.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_feature_set(
        self,
        dataset_id: uuid.UUID,
        name: str,
        features: list[dict],
        output_file_path: str | None = None,
        feature_count: int = 0,
        method: str = "",
    ) -> FeatureSet:
        """Insert a new feature set record."""
        feature_set = FeatureSet(
            dataset_id=dataset_id,
            name=name,
            features=features,
            output_file_path=output_file_path,
            feature_count=feature_count,
            method=method,
        )
        self.db.add(feature_set)
        await self.db.flush()
        return feature_set

    async def delete_feature_set(self, feature_set_id: uuid.UUID) -> bool:
        """Delete a feature set record. Returns True if deleted."""
        feature_set = await self.get_by_id(feature_set_id)
        if not feature_set:
            return False
        await self.db.delete(feature_set)
        await self.db.flush()
        return True
