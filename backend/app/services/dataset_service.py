"""Business logic for dataset ingestion and management.

Orchestrates file I/O, hash computation, Pandas parsing for metadata
extraction, and repository persistence. This is the core data ingestion
pipeline that feeds all downstream ML operations.
"""

import hashlib
import logging
import uuid
from pathlib import Path

import pandas as pd
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.dataset import Dataset
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dataset import DatasetPreview

logger = logging.getLogger(__name__)
settings = get_settings()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_UPLOAD_SIZE = settings.MAX_UPLOAD_SIZE  # 100 MB default


class DatasetService:
    """Handles dataset upload, preview, listing, and deletion."""

    def __init__(self, db: AsyncSession) -> None:
        self.repo = DatasetRepository(db)

    # Upload

    async def upload_dataset(
        self,
        user_id: uuid.UUID,
        file: UploadFile,
        description: str | None = None,
    ) -> Dataset:
        """Ingest an uploaded file: validate, hash, parse, store, persist.

        Pipeline:
            1. Validate extension (.csv / .xlsx / .xls)
            2. Read file bytes and enforce size limit
            3. Compute SHA-256 hash and check for duplicates
            4. Parse with Pandas to extract row_count, column_count, column_names
            5. Save file to disk under storage/uploads/<uuid>.<ext>
            6. Persist metadata to the database

        Raises:
            BadRequestException: Invalid file type or size exceeded.
            ConflictException: Duplicate file already uploaded by this user.
        """
        # 1. Validate extension
        filename = file.filename or "unknown"
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise BadRequestException(
                detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # 2. Read content and check size
        content = await file.read()
        file_size = len(content)
        if file_size == 0:
            raise BadRequestException(detail="Uploaded file is empty")
        if file_size > MAX_UPLOAD_SIZE:
            raise BadRequestException(
                detail=f"File size ({file_size // (1024*1024)} MB) exceeds {MAX_UPLOAD_SIZE // (1024*1024)} MB limit"
            )

        # 3. Hash and dedup check
        file_hash = hashlib.sha256(content).hexdigest()
        existing = await self.repo.get_by_hash(file_hash, user_id)
        if existing:
            raise ConflictException(
                detail=f"Duplicate file — this dataset was already uploaded as '{existing.name}'"
            )

        # 4. Parse with Pandas to extract metadata
        row_count, column_count, column_names = self._parse_metadata(content, ext)

        # 5. Save to disk
        file_id = uuid.uuid4()
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        stored_filename = f"{file_id}{ext}"
        stored_path = upload_dir / stored_filename
        stored_path.write_bytes(content)
        logger.info("Saved dataset file: %s (%d bytes)", stored_path, file_size)

        # 6. Persist to database
        dataset = await self.repo.create_dataset(
            user_id=user_id,
            name=filename,
            file_path=str(stored_path),
            file_size=file_size,
            file_hash=file_hash,
            file_type=ext.lstrip("."),
            row_count=row_count,
            column_count=column_count,
            column_names=column_names,
            description=description,
        )
        logger.info("Dataset ingested: %s (id=%s, %d rows, %d cols)", filename, dataset.id, row_count or 0, column_count or 0)
        return dataset

    # Preview

    async def preview_dataset(
        self, dataset_id: uuid.UUID, user_id: uuid.UUID, n_rows: int = 10
    ) -> DatasetPreview:
        """Load first N rows of a dataset for preview.

        Uses Pandas to read the stored file and return a structured
        preview suitable for rendering in a frontend table.

        Raises:
            NotFoundException: Dataset not found or not owned by user.
        """
        ds = await self.repo.get_by_id(dataset_id, user_id)
        if not ds:
            raise NotFoundException(detail="Dataset not found")

        file_path = Path(ds.file_path)
        if not file_path.exists():
            raise NotFoundException(detail="Dataset file missing from storage")

        ext = f".{ds.file_type}"
        df = self._read_dataframe(file_path, ext, nrows=n_rows)

        # Replace NaN/NaT with None for JSON serialisation
        df = df.where(df.notna(), None)

        return DatasetPreview(
            columns=list(df.columns),
            rows=df.to_dict(orient="records"),
            total_rows=ds.row_count or 0,
        )

    # List

    async def list_datasets(self, user_id: uuid.UUID) -> list[Dataset]:
        """Return all datasets for the user."""
        return await self.repo.list_by_user(user_id)

    # Detail

    async def get_dataset(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> Dataset:
        """Get a single dataset's metadata."""
        ds = await self.repo.get_by_id(dataset_id, user_id)
        if not ds:
            raise NotFoundException(detail="Dataset not found")
        return ds

    # Delete

    async def delete_dataset(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a dataset: remove file from disk and record from DB.

        Raises:
            NotFoundException: Dataset not found or not owned by user.
        """
        ds = await self.repo.get_by_id(dataset_id, user_id)
        if not ds:
            raise NotFoundException(detail="Dataset not found")

        # Remove file from disk
        file_path = Path(ds.file_path)
        if file_path.exists():
            file_path.unlink()
            logger.info("Deleted file: %s", file_path)

        # Remove trained-model files of experiments on this dataset (DB rows cascade)
        from app.repositories.experiment_repository import ExperimentRepository
        from app.services.experiment_service import remove_experiment_artifacts

        for experiment_id in await ExperimentRepository(self.repo.db).list_ids_for_dataset(dataset_id):
            remove_experiment_artifacts(experiment_id)

        # Remove DB record
        await self.repo.delete_dataset(dataset_id, user_id)
        logger.info("Dataset deleted: %s (id=%s)", ds.name, ds.id)

    # Internal helpers

    @staticmethod
    def _parse_metadata(content: bytes, ext: str) -> tuple[int | None, int | None, list[str] | None]:
        """Parse uploaded file bytes to extract row count, column count, and column names.

        This is the first stage of the ML data ingestion pipeline —
        understanding the shape and structure of the incoming data.
        """
        try:
            import io

            if ext == ".csv":
                df = pd.read_csv(io.BytesIO(content), nrows=0)  # Just headers
                # Count rows separately (more memory efficient for large files)
                row_count = sum(1 for _ in io.BytesIO(content)) - 1  # subtract header
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(io.BytesIO(content), nrows=0)
                df_full = pd.read_excel(io.BytesIO(content))
                row_count = len(df_full)
            else:
                return None, None, None

            column_names = list(df.columns.astype(str))
            column_count = len(column_names)
            return max(row_count, 0), column_count, column_names

        except Exception as e:
            logger.warning("Failed to parse dataset metadata: %s", e)
            return None, None, None

    @staticmethod
    def _read_dataframe(file_path: Path, ext: str, nrows: int = 10) -> pd.DataFrame:
        """Read a stored dataset file into a Pandas DataFrame (limited rows)."""
        if ext == ".csv":
            return pd.read_csv(file_path, nrows=nrows)
        elif ext in (".xlsx", ".xls"):
            return pd.read_excel(file_path, nrows=nrows)
        else:
            raise BadRequestException(detail=f"Cannot read file type: {ext}")
