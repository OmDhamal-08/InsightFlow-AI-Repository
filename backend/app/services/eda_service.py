"""Business logic for Exploratory Data Analysis (EDA).

Handles dataset ownership, triggers auto-generated summary dashboard charts,
and dynamically computes column normality distribution curves, boxplots, scatters,
and QQ-plots.
"""

import logging
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, BadRequestException
from app.ml.eda_generator import EdaGenerator
from app.models.dataset import Dataset
from app.models.eda import EdaResult
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.eda_repository import EdaRepository
from app.services.profiling_service import ProfilingService

logger = logging.getLogger(__name__)


class EdaService:
    """Orchestrates EDA calculations and database persistence."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.eda_repo = EdaRepository(db)
        self.profiling_service = ProfilingService(db)

    async def run_summary_eda(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> list[EdaResult]:
        """Trigger auto-generation of overview panel charts (heatmaps, missing values, categories).

        Updates dataset status to 'eda_completed'.
        """
        dataset = await self._verify_dataset(dataset_id, user_id)
        df = self._load_dataframe(dataset)

        # Retrieve or run profiling for column types
        try:
            profile_result = await self.profiling_service.get_profiling(dataset_id, user_id)
            column_types = profile_result.column_types
        except NotFoundException:
            logger.info("Dataset=%s not profiled yet. Triggering profiling prior to EDA audit.", dataset_id)
            profile_result = await self.profiling_service.run_profiling(dataset_id, user_id)
            column_types = profile_result.column_types

        logger.info("Computing EDA summary dashboard for dataset=%s", dataset_id)
        charts_list = EdaGenerator.generate_summary(df, column_types)

        # Save to database
        saved_charts = await self.eda_repo.bulk_create(dataset_id, charts_list)

        # Update dataset status
        dataset.status = "eda_completed"

        return saved_charts

    async def get_custom_plot(
        self, dataset_id: uuid.UUID, user_id: uuid.UUID, chart_type: str, columns: list[str]
    ) -> dict:
        """Dynamically compute a custom plot (normality distributions, boxplots, scatters, QQ-plots) in-memory.

        Does not store results in the database (transient).
        """
        dataset = await self._verify_dataset(dataset_id, user_id)
        df = self._load_dataframe(dataset)

        # Get column types from profiling
        try:
            profile_result = await self.profiling_service.get_profiling(dataset_id, user_id)
            column_types = profile_result.column_types
        except NotFoundException:
            profile_result = await self.profiling_service.run_profiling(dataset_id, user_id)
            column_types = profile_result.column_types

        logger.info("Dynamically computing custom EDA plot '%s' for dataset=%s", chart_type, dataset_id)
        plot_result = EdaGenerator.generate_custom_plot(df, chart_type, columns, column_types)
        
        if "error" in plot_result:
            raise BadRequestException(detail=plot_result["error"])

        return plot_result

    async def list_summary_eda(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> list[EdaResult]:
        """Fetch pre-calculated EDA overview dashboard results.

        Raises:
            NotFoundException: If dataset does not exist.
        """
        await self._verify_dataset(dataset_id, user_id)
        return await self.eda_repo.list_by_dataset(dataset_id)

    async def get_bivariate_analysis(
        self, dataset_id: uuid.UUID, user_id: uuid.UUID, target_column: str
    ) -> dict:
        """Compute target-aware bivariate statistical associations for all features vs. a target column.

        Returns statistical test results (Pearson, ANOVA, Chi-Square, Cramér's V)
        and bivariate chart data for Plotly rendering.
        """
        dataset = await self._verify_dataset(dataset_id, user_id)
        df = self._load_dataframe(dataset)

        if target_column not in df.columns:
            raise BadRequestException(detail=f"Target column '{target_column}' not found in dataset.")

        # Get column types from profiling
        try:
            profile_result = await self.profiling_service.get_profiling(dataset_id, user_id)
            column_types = profile_result.column_types
        except NotFoundException:
            profile_result = await self.profiling_service.run_profiling(dataset_id, user_id)
            column_types = profile_result.column_types

        logger.info("Computing bivariate analysis for target='%s' on dataset=%s", target_column, dataset_id)
        return EdaGenerator.generate_bivariate_analysis(df, target_column, column_types)

    # Helpers

    async def _verify_dataset(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> Dataset:
        """Fetch dataset and verify user ownership."""
        dataset = await self.dataset_repo.get_by_id(dataset_id, user_id)
        if not dataset:
            raise NotFoundException(detail="Dataset not found")
        return dataset

    @staticmethod
    def _load_dataframe(dataset: Dataset) -> pd.DataFrame:
        """Read original dataset from disk into a Pandas DataFrame."""
        file_path = Path(dataset.file_path)
        if not file_path.exists():
            raise NotFoundException(detail="Dataset file missing from storage")

        try:
            if dataset.file_type == "csv":
                return pd.read_csv(file_path)
            elif dataset.file_type in ("xlsx", "xls"):
                return pd.read_excel(file_path)
            else:
                raise BadRequestException(detail=f"Unsupported file type: {dataset.file_type}")
        except Exception as e:
            logger.error("Failed to load dataset file: %s", e)
            raise BadRequestException(detail=f"Could not load dataset file: {str(e)}")
