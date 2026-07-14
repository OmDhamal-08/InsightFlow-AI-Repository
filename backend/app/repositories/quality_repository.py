"""Data access layer for QualityResult model."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quality import QualityResult


class QualityRepository:
    """CRUD operations for dataset quality analysis results."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_dataset_id(self, dataset_id: uuid.UUID) -> QualityResult | None:
        """Fetch the quality results associated with a dataset."""
        stmt = select(QualityResult).where(QualityResult.dataset_id == dataset_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        dataset_id: uuid.UUID,
        quality_score: float,
        missing_value_report: dict,
        duplicate_report: dict,
        outlier_report: dict,
        correlation_report: dict,
        skewness_report: dict,
        imbalance_report: dict | None,
        recommendations: list,
    ) -> QualityResult:
        """Save a new quality analysis result, replacing any existing one for this dataset."""
        existing = await self.get_by_dataset_id(dataset_id)
        if existing:
            existing.quality_score = quality_score
            existing.missing_value_report = missing_value_report
            existing.duplicate_report = duplicate_report
            existing.outlier_report = outlier_report
            existing.correlation_report = correlation_report
            existing.skewness_report = skewness_report
            existing.imbalance_report = imbalance_report
            existing.recommendations = recommendations
            await self.db.flush()
            return existing

        quality = QualityResult(
            dataset_id=dataset_id,
            quality_score=quality_score,
            missing_value_report=missing_value_report,
            duplicate_report=duplicate_report,
            outlier_report=outlier_report,
            correlation_report=correlation_report,
            skewness_report=skewness_report,
            imbalance_report=imbalance_report,
            recommendations=recommendations,
        )
        self.db.add(quality)
        await self.db.flush()
        return quality

    async def delete_by_dataset_id(self, dataset_id: uuid.UUID) -> bool:
        """Delete a dataset's quality results. Returns True if found & deleted."""
        quality = await self.get_by_dataset_id(dataset_id)
        if not quality:
            return False
        await self.db.delete(quality)
        await self.db.flush()
        return True
