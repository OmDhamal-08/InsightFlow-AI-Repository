"""Dataset API endpoints.

Routes:
    POST   /upload         — Upload a new CSV/Excel dataset
    GET    /               — List all datasets for the user
    GET    /{id}           — Get dataset metadata
    GET    /{id}/preview   — Preview first N rows
    DELETE /{id}           — Delete a dataset (file + record)
    GET    /{id}/download  — Download original file
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.dataset import DatasetPreview, DatasetRead
from app.services.dataset_service import DatasetService

router = APIRouter()


@router.post("/upload", response_model=DatasetRead, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    description: str = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a CSV or Excel dataset.

    The ingestion pipeline validates the file, computes a SHA-256 hash
    for duplicate detection, parses the data with Pandas to extract
    metadata (row count, column count, column names), saves the original
    file to disk, and persists the record in the database.
    """
    service = DatasetService(db)
    dataset = await service.upload_dataset(
        user_id=current_user.id,
        file=file,
        description=description,
    )
    await db.commit()
    return dataset


@router.get("/", response_model=list[DatasetRead])
async def list_datasets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all datasets belonging to the authenticated user."""
    service = DatasetService(db)
    return await service.list_datasets(current_user.id)


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve metadata for a specific dataset."""
    service = DatasetService(db)
    return await service.get_dataset(dataset_id, current_user.id)


@router.get("/{dataset_id}/preview", response_model=DatasetPreview)
async def preview_dataset(
    dataset_id: uuid.UUID,
    rows: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Preview the first N rows of a dataset.

    Uses Pandas to read the stored file and return column names
    and row data suitable for rendering in a frontend table.
    """
    service = DatasetService(db)
    return await service.preview_dataset(dataset_id, current_user.id, n_rows=rows)


@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a dataset: removes the file from disk and the database record."""
    service = DatasetService(db)
    await service.delete_dataset(dataset_id, current_user.id)
    await db.commit()


@router.get("/{dataset_id}/download")
async def download_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the original uploaded file."""
    service = DatasetService(db)
    dataset = await service.get_dataset(dataset_id, current_user.id)
    return FileResponse(
        path=dataset.file_path,
        filename=dataset.name,
        media_type="application/octet-stream",
    )
