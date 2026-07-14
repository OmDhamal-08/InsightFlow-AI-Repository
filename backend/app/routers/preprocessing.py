"""Preprocessing API endpoints.

Routes:
    POST /datasets/{id}/preprocess/analyze — Get quality recommendations list
    POST /datasets/{id}/preprocess/preview — Preview transformation sample
    POST /datasets/{id}/preprocess/apply   — Execute steps, save file, and register dataset
    GET  /datasets/{id}/preprocess/pipelines — List saved pipelines
    GET  /datasets/{id}/preprocess/pipelines/{pid} — Detail of a pipeline
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.pipeline import (
    PipelineApplyRequest,
    PipelinePreviewRequest,
    PipelinePreviewResponse,
    PipelineRead,
)
from app.services.preprocessing_service import PreprocessingService

router = APIRouter()


@router.post("/{dataset_id}/preprocess/analyze", response_model=list[dict])
async def get_recommendations(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve recommended preprocessing actions from the data quality engine."""
    service = PreprocessingService(db)
    return await service.get_recommendations(dataset_id, current_user.id)


@router.post("/{dataset_id}/preprocess/preview", response_model=PipelinePreviewResponse)
async def preview_pipeline(
    dataset_id: uuid.UUID,
    req: PipelinePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a before/after preview of the selected preprocessing steps.

    Applies the steps to a copy of the dataset and returns statistical summaries
    and sample rows before vs after.
    """
    service = PreprocessingService(db)
    # Convert Pydantic steps list to dict list
    steps_list = [step.model_dump() for step in req.steps]
    return await service.preview_pipeline(dataset_id, current_user.id, steps_list)


@router.post("/{dataset_id}/preprocess/apply", response_model=PipelineRead, status_code=201)
async def apply_pipeline(
    dataset_id: uuid.UUID,
    req: PipelineApplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute preprocessing pipeline, save the preprocessed file on disk, and register it.

    Generates a new Dataset in the database with status 'processed' and saves
    the pipeline configuration details.
    """
    service = PreprocessingService(db)
    steps_list = [step.model_dump() for step in req.steps]
    result = await service.apply_pipeline(
        dataset_id=dataset_id,
        user_id=current_user.id,
        name=req.name,
        steps=steps_list,
    )
    await db.commit()
    return result


@router.get("/{dataset_id}/preprocess/pipelines", response_model=list[PipelineRead])
async def list_pipelines(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all preprocessing pipelines created for this dataset."""
    service = PreprocessingService(db)
    return await service.list_pipelines(dataset_id, current_user.id)


@router.get("/{dataset_id}/preprocess/pipelines/{pipeline_id}", response_model=PipelineRead)
async def get_pipeline(
    dataset_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of a specific preprocessing pipeline."""
    service = PreprocessingService(db)
    return await service.get_pipeline(dataset_id, pipeline_id, current_user.id)
