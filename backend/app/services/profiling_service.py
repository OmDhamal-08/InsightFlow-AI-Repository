"""Business logic for dataset profiling.

Handles dataset ownership verification, raw file loading (CSV/Excel),
triggering the dataset profiling analysis, saving results to the DB,
and updating the dataset status to 'profiled'.
"""

import logging
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, BadRequestException
from app.ml.profiler import DatasetProfiler
from app.models.profiling import ProfilingResult
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.profiling_repository import ProfilingRepository

logger = logging.getLogger(__name__)


class ProfilingService:
    """Orchestrates dataset profiling operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.profiling_repo = ProfilingRepository(db)

    async def run_profiling(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> ProfilingResult:
        """Trigger analysis on a dataset: load file, compute profile, save results.

        Updates dataset status to 'profiled'.

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

        # 3. Load DataFrame
        try:
            if dataset.file_type == "csv":
                df = pd.read_csv(file_path)
            elif dataset.file_type in ("xlsx", "xls"):
                df = pd.read_excel(file_path)
            else:
                raise BadRequestException(detail=f"Unsupported file type: {dataset.file_type}")
        except Exception as e:
            logger.error("Failed to parse dataset for profiling: %s", e)
            raise BadRequestException(detail=f"Could not parse dataset file: {str(e)}")

        # 4. Perform profiling analysis
        logger.info("Starting profiling for dataset=%s (%d rows)", dataset_id, len(df))
        profile_data = DatasetProfiler.profile(df)

        # 5. Persist profile results
        result = await self.profiling_repo.create_or_update(
            dataset_id=dataset_id,
            column_types=profile_data["column_types"],
            null_counts=profile_data["null_counts"],
            unique_counts=profile_data["unique_counts"],
            duplicate_row_count=profile_data["duplicate_row_count"],
            descriptive_stats=profile_data["descriptive_stats"],
            total_rows=profile_data["total_rows"],
            total_columns=profile_data["total_columns"],
        )

        # 6. Update dataset status & counts if not already captured
        dataset.status = "profiled"
        dataset.row_count = profile_data["total_rows"]
        dataset.column_count = profile_data["total_columns"]
        dataset.column_names = list(df.columns.astype(str))

        logger.info("Successfully profiled dataset=%s", dataset_id)
        return result

    async def get_profiling(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> ProfilingResult:
        """Fetch the profiling result for a dataset.

        Raises:
            NotFoundException: If dataset or profiling result does not exist.
        """
        # Verify ownership
        dataset = await self.dataset_repo.get_by_id(dataset_id, user_id)
        if not dataset:
            raise NotFoundException(detail="Dataset not found")

        result = await self.profiling_repo.get_by_dataset_id(dataset_id)
        if not result:
            raise NotFoundException(detail="Profiling results not found for this dataset")

        return result
