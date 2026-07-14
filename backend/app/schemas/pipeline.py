"""Pydantic schemas for preprocessing pipelines."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class PipelineStep(BaseModel):
    """Represents a single preprocessing step action."""

    action: str
    column: str | None = None
    params: dict | None = None


class PipelinePreviewRequest(BaseModel):
    """Request schema to preview transformations."""

    steps: list[PipelineStep]


class PipelineApplyRequest(BaseModel):
    """Request schema to save and execute a preprocessing pipeline."""

    name: str = Field(..., max_length=255)
    steps: list[PipelineStep]


class PipelineRead(BaseModel):
    """Pipeline details metadata response."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    name: str
    steps: list[dict]
    config: dict
    output_file_path: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PipelinePreviewResponse(BaseModel):
    """Detailed before/after previews response."""

    before: dict
    after: dict
