"""Pydantic schemas for Dataset read/write operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DatasetRead(BaseModel):
    """Dataset metadata returned by list/detail endpoints."""

    id: uuid.UUID
    name: str
    description: str | None = None
    file_size: int
    file_type: str
    row_count: int | None = None
    column_count: int | None = None
    column_names: list[str] | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetPreview(BaseModel):
    """Preview of dataset rows."""

    columns: list[str]
    rows: list[dict]
    total_rows: int
