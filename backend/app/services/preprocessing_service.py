"""Business logic for dataset preprocessing.

Orchestrates loading raw files, generating before/after previews, applying
sequential transforms, saving the cleaned file to disk, registering it
as a new dataset, and logging the pipeline metadata.
"""

import hashlib
import logging
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, BadRequestException
from app.ml.preprocessor import DatasetPreprocessor, PreprocessingError
from app.models.dataset import Dataset
from app.models.pipeline import PreprocessingPipeline
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.pipeline_repository import PipelineRepository
from app.services.quality_service import QualityService

logger = logging.getLogger(__name__)


class PreprocessingService:
    """Handles pipeline configuration, preview, execution, and registration."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.pipeline_repo = PipelineRepository(db)
        self.quality_service = QualityService(db)

    async def get_recommendations(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
        """Fetch data quality recommendations to pre-populate the wizard.

        Triggers quality audit automatically if it hasn't been executed yet.
        """
        try:
            quality_result = await self.quality_service.get_quality_analysis(dataset_id, user_id)
            return quality_result.recommendations
        except NotFoundException:
            logger.info("Dataset=%s has no quality audit. Triggering audit to retrieve recommendations.", dataset_id)
            quality_result = await self.quality_service.run_quality_analysis(dataset_id, user_id)
            return quality_result.recommendations

    async def preview_pipeline(
        self, dataset_id: uuid.UUID, user_id: uuid.UUID, steps: list[dict]
    ) -> dict:
        """Run transformation preview on a sample of the dataset."""
        dataset = await self._verify_dataset(dataset_id, user_id)
        df = self._load_dataframe(dataset)
        try:
            return DatasetPreprocessor.preview(df, steps)
        except PreprocessingError as exc:
            raise BadRequestException(detail=str(exc)) from exc

    async def apply_pipeline(
        self,
        dataset_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        steps: list[dict],
    ) -> PreprocessingPipeline:
        """Execute the preprocessing steps, write file, and register processed dataset.

        Returns:
            The saved PreprocessingPipeline database object.
        """
        dataset = await self._verify_dataset(dataset_id, user_id)
        df = self._load_dataframe(dataset)

        logger.info("Applying %d preprocessing steps to dataset=%s", len(steps), dataset_id)
        try:
            processed_df, config_params = DatasetPreprocessor.apply(df, steps)
        except PreprocessingError as exc:
            raise BadRequestException(detail=str(exc)) from exc
        if processed_df.empty:
            raise BadRequestException(detail="These steps remove every row — nothing would be left to save.")

        # Write output file
        file_id = uuid.uuid4()
        parent_dir = Path(dataset.file_path).parent
        file_ext = ".csv"  # Always save processed datasets as clean CSV for downstream ML models
        output_filename = f"{file_id}_cleaned{file_ext}"
        output_path = parent_dir / output_filename
        
        processed_df.to_csv(output_path, index=False)
        file_size = output_path.stat().st_size

        # Compute SHA-256 hash
        file_bytes = output_path.read_bytes()
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Register processed dataset
        processed_dataset = await self.dataset_repo.create_dataset(
            user_id=user_id,
            name=f"{Path(dataset.name).stem}_cleaned.csv",
            file_path=str(output_path),
            file_size=file_size,
            file_hash=file_hash,
            file_type="csv",
            row_count=len(processed_df),
            column_count=len(processed_df.columns),
            column_names=list(processed_df.columns.astype(str)),
            description=f"Preprocessed version of dataset '{dataset.name}' using pipeline '{name}'.",
        )
        
        # Mark dataset status as processed
        processed_dataset.status = "processed"

        # Create pipeline record
        pipeline = await self.pipeline_repo.create_pipeline(
            dataset_id=dataset_id,
            name=name,
            steps=steps,
            config=config_params,
            output_file_path=str(output_path),
            status="applied",
        )

        logger.info("Successfully applied preprocessing pipeline id=%s. Cleaned dataset registered: id=%s", pipeline.id, processed_dataset.id)
        return pipeline

    async def list_pipelines(
        self, dataset_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[PreprocessingPipeline]:
        """List all preprocessing pipelines created for a dataset."""
        await self._verify_dataset(dataset_id, user_id)
        return await self.pipeline_repo.list_by_dataset(dataset_id)

    async def get_pipeline(
        self, dataset_id: uuid.UUID, pipeline_id: uuid.UUID, user_id: uuid.UUID
    ) -> PreprocessingPipeline:
        """Retrieve details of a specific pipeline."""
        await self._verify_dataset(dataset_id, user_id)
        pipeline = await self.pipeline_repo.get_by_id(pipeline_id)
        if not pipeline or pipeline.dataset_id != dataset_id:
            raise NotFoundException(detail="Preprocessing pipeline not found")
        return pipeline

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
