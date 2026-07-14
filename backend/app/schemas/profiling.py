"""Pydantic schemas for dataset profiling results."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ProfilingResultRead(BaseModel):
    """Profiling results metadata and stats."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    column_types: dict[str, str]
    null_counts: dict[str, int]
    unique_counts: dict[str, int]
    duplicate_row_count: int
    descriptive_stats: dict[str, dict]
    total_rows: int
    total_columns: int
    created_at: datetime

    model_config = {"from_attributes": True}
