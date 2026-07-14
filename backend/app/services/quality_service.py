"""Business logic for dataset quality analysis.

Ensures dataset ownership, checks for (or triggers) dataset profiling
to obtain column types, loads raw data, triggers multidimensional quality metrics
computation, and persists the analysis results.
"""

import logging
import os
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, BadRequestException
from app.ml.quality_analyzer import DataQualityAnalyzer
from app.models.quality import QualityResult
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.quality_repository import QualityRepository
from app.services.profiling_service import ProfilingService

logger = logging.getLogger(__name__)


class QualityService:
    """Orchestrates dataset data quality audits."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.quality_repo = QualityRepository(db)
        self.profiling_service = ProfilingService(db)

    async def run_quality_analysis(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> QualityResult:
        """Run multidimensional quality analysis on a dataset.

        Retrieves column types from profiling results. If the dataset has not
        been profiled yet, profiling is automatically executed first.

        Raises:
            NotFoundException: If dataset is not found.
            BadRequestException: If file is missing or unparseable.
        """
        # 1. Fetch dataset and verify ownership
        dataset = await self.dataset_repo.get_by_id(dataset_id, user_id)
        if not dataset:
            raise NotFoundException(detail="Dataset not found")

        # 2. Check file path on disk
        file_path = Path(dataset.file_path)
        if not file_path.exists():
            raise NotFoundException(detail="Dataset file missing from storage")

        # 3. Retrieve or run profiling to get column types
        try:
            profile_result = await self.profiling_service.get_profiling(dataset_id, user_id)
            column_types = profile_result.column_types
        except NotFoundException:
            logger.info("Dataset=%s not profiled yet. Triggering profiling prior to quality audit.", dataset_id)
            profile_result = await self.profiling_service.run_profiling(dataset_id, user_id)
            column_types = profile_result.column_types

        # 4. Load DataFrame
        try:
            if dataset.file_type == "csv":
                df = pd.read_csv(file_path)
            elif dataset.file_type in ("xlsx", "xls"):
                df = pd.read_excel(file_path)
            else:
                raise BadRequestException(detail=f"Unsupported file type: {dataset.file_type}")
        except Exception as e:
            logger.error("Failed to parse dataset for quality analysis: %s", e)
            raise BadRequestException(detail=f"Could not parse dataset file: {str(e)}")

        # 5. Run quality audit calculations
        logger.info("Starting quality analysis for dataset=%s", dataset_id)
        analysis_data = DataQualityAnalyzer.analyze(df, column_types)

        # 6. Save results to database
        result = await self.quality_repo.create_or_update(
            dataset_id=dataset_id,
            quality_score=analysis_data["quality_score"],
            missing_value_report=analysis_data["missing_value_report"],
            duplicate_report=analysis_data["duplicate_report"],
            outlier_report=analysis_data["outlier_report"],
            correlation_report=analysis_data["correlation_report"],
            skewness_report=analysis_data["skewness_report"],
            imbalance_report=analysis_data["imbalance_report"],
            recommendations=analysis_data["recommendations"],
        )

        # Update dataset status
        dataset.status = "quality_analyzed"

        logger.info("Successfully audited data quality for dataset=%s. Score: %.2f", dataset_id, result.quality_score)
        return result

    async def get_quality_analysis(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> QualityResult:
        """Fetch the data quality results for a dataset.

        Raises:
            NotFoundException: If dataset or quality results do not exist.
        """
        # Verify ownership
        dataset = await self.dataset_repo.get_by_id(dataset_id, user_id)
        if not dataset:
            raise NotFoundException(detail="Dataset not found")

        result = await self.quality_repo.get_by_dataset_id(dataset_id)
        if not result:
            raise NotFoundException(detail="Data quality results not found for this dataset")

        return result
