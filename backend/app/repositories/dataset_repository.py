"""Data access layer for Dataset model.

All database queries related to datasets are centralised here.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import Dataset


class DatasetRepository:
    """CRUD operations for datasets."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> Dataset | None:
        """Fetch a dataset by ID, scoped to the owning user."""
        stmt = select(Dataset).where(
            Dataset.id == dataset_id, Dataset.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_hash(self, file_hash: str, user_id: uuid.UUID) -> Dataset | None:
        """Check if the user already uploaded a file with this SHA-256 hash."""
        stmt = select(Dataset).where(
            Dataset.file_hash == file_hash, Dataset.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[Dataset]:
        """Return all datasets belonging to a user, newest first."""
        stmt = (
            select(Dataset)
            .where(Dataset.user_id == user_id)
            .order_by(Dataset.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_dataset(
        self,
        user_id: uuid.UUID,
        name: str,
        file_path: str,
        file_size: int,
        file_hash: str,
        file_type: str,
        row_count: int | None = None,
        column_count: int | None = None,
        column_names: list[str] | None = None,
        description: str | None = None,
    ) -> Dataset:
        """Insert a new dataset record."""
        ds = Dataset(
            user_id=user_id,
            name=name,
            description=description,
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            file_type=file_type,
            row_count=row_count,
            column_count=column_count,
            column_names=column_names,
        )
        self.db.add(ds)
        await self.db.flush()
        return ds

    async def delete_dataset(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a dataset record. Returns True if found and deleted."""
        ds = await self.get_by_id(dataset_id, user_id)
        if not ds:
            return False
        await self.db.delete(ds)
        await self.db.flush()
        return True
