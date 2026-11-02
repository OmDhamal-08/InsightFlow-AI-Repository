"""Business logic for feature engineering.

Orchestrates loading datasets, calculating engineered columns (date splits,
numeric interaction math, PCA projections, Mutual Information rankings),
saving transformed files, and registering them as new datasets.
"""

import hashlib
import logging
import os
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, BadRequestException
from app.ml.feature_engineer import FeatureEngineer
from app.models.dataset import Dataset
from app.models.feature import FeatureSet
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.feature_repository import FeatureRepository

logger = logging.getLogger(__name__)


class FeatureService:
    """Handles feature engineering runs, dataset updates, and metadata logging."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_repo = DatasetRepository(db)
        self.feature_repo = FeatureRepository(db)

    async def generate_feature_set(
        self,
        dataset_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        method: str,
        config: dict,
    ) -> tuple[FeatureSet, dict]:
        """Verify, run feature engineering preview, and register the FeatureSet metadata.

        Returns:
            The created FeatureSet and a preview dictionary of the generated columns.
        """
        dataset = await self._verify_dataset(dataset_id, user_id)
        df = self._load_dataframe(dataset)

        logger.info("Generating feature set preview method='%s' for dataset=%s", method, dataset_id)
        processed_df, engineered_list = FeatureEngineer.generate_features(df, method, config)

        if not engineered_list:
            raise BadRequestException(
                detail="No features were engineered. Ensure columns are correctly selected and valid for this method."
            )

        # Create transient metadata in database
        feature_set = await self.feature_repo.create_feature_set(
            dataset_id=dataset_id,
            name=name,
            features=engineered_list,
            feature_count=len(engineered_list),
            method=method,
        )

        # Get preview rows of engineered columns (first 5 rows)
        new_col_names = [f["name"] for f in engineered_list]
        
        # If method is 'selection', all other features are dropped, so we return the final df structure
        preview_df = processed_df if method == "selection" else processed_df[new_col_names]
        
        preview_rows_raw = preview_df.head(5).to_dict(orient="records")
        
        import numpy as np
        def to_json_val(v):
            if pd.isna(v):
                return None
            if isinstance(v, (np.integer, np.int64, np.int32, np.int16, np.int8)):
                return int(v)
            if isinstance(v, (np.floating, np.float64, np.float32)):
                return float(v)
            return v
            
        preview_rows = [{k: to_json_val(v) for k, v in row.items()} for row in preview_rows_raw]

        preview_response = {
            "columns": list(preview_df.columns),
            "rows": preview_rows,
        }

        return feature_set, preview_response

    async def apply_feature_set(
        self, dataset_id: uuid.UUID, feature_set_id: uuid.UUID, user_id: uuid.UUID
    ) -> FeatureSet:
        """Run feature engineering on the whole dataset, save output, and register new dataset.

        Returns:
            The updated FeatureSet pointing to the output file.
        """
        dataset = await self._verify_dataset(dataset_id, user_id)
        feature_set = await self.feature_repo.get_by_id(feature_set_id)

        if not feature_set or feature_set.dataset_id != dataset_id:
            raise NotFoundException(detail="Feature set not found")

        if feature_set.output_file_path:
            raise BadRequestException(detail="This feature set has already been applied.")

        df = self._load_dataframe(dataset)

        # Rebuild the generation config from the stored feature definitions
        parents: list[str] = []
        for feature in feature_set.features:
            for parent in feature.get("parent_columns", []):
                if parent not in parents:
                    parents.append(parent)

        logger.info("Applying feature engineering set id=%s to dataset=%s", feature_set_id, dataset_id)
        if feature_set.method == "selection":
            target = feature_set.features[0].get("target_column")
            if not target or target not in df.columns:
                raise BadRequestException(
                    detail="This selection set has no recorded target column — please generate it again."
                )
            cols_to_keep = [f["name"] for f in feature_set.features if f["name"] in df.columns] + [target]
            processed_df = df[cols_to_keep]
        else:
            if feature_set.method in ("date", "text"):
                config = {"column": parents[0]}
            elif feature_set.method == "pca":
                config = {"columns": parents, "n_components": feature_set.feature_count}
            else:  # interaction, polynomial
                config = {"columns": parents}
            processed_df, produced = FeatureEngineer.generate_features(df, feature_set.method, config)
            if not produced:
                raise BadRequestException(detail="Feature engineering produced no columns on the full dataset.")

        # Save output file
        file_id = uuid.uuid4()
        parent_dir = Path(dataset.file_path).parent
        file_ext = ".csv"
        output_filename = f"{file_id}_engineered{file_ext}"
        output_path = parent_dir / output_filename

        processed_df.to_csv(output_path, index=False)
        file_size = output_path.stat().st_size

        # Compute SHA-256 hash
        file_bytes = output_path.read_bytes()
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Register engineered dataset
        engineered_dataset = await self.dataset_repo.create_dataset(
            user_id=user_id,
            name=f"{Path(dataset.name).stem}_engineered.csv",
            file_path=str(output_path),
            file_size=file_size,
            file_hash=file_hash,
            file_type="csv",
            row_count=len(processed_df),
            column_count=len(processed_df.columns),
            column_names=list(processed_df.columns.astype(str)),
            description=f"Feature-engineered version of dataset '{dataset.name}' using set '{feature_set.name}' via '{feature_set.method}'.",
        )

        engineered_dataset.status = "processed"

        # Update feature set output path
        feature_set.output_file_path = str(output_path)

        logger.info("Successfully applied feature set. Engineered dataset registered: id=%s", engineered_dataset.id)
        return feature_set

    async def list_feature_sets(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> list[FeatureSet]:
        """Fetch all feature sets created for a dataset."""
        await self._verify_dataset(dataset_id, user_id)
        return await self.feature_repo.list_by_dataset(dataset_id)

    async def get_feature_set(
        self, dataset_id: uuid.UUID, feature_set_id: uuid.UUID, user_id: uuid.UUID
    ) -> FeatureSet:
        """Retrieve details of a specific feature set."""
        await self._verify_dataset(dataset_id, user_id)
        feature_set = await self.feature_repo.get_by_id(feature_set_id)
        if not feature_set or feature_set.dataset_id != dataset_id:
            raise NotFoundException(detail="Feature set not found")
        return feature_set

    # ── Helpers ──────────────────────────────────────────────────

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
