"""AutoML experiment API (Phase 10) and model evaluation API (Phase 11).

Routes (prefix ``/api/v1/experiments``):
    GET    /recommend?dataset_id=&target_column=   — detect task, suggest algorithms
    POST   /                                       — train & compare models
    GET    /                                       — list experiments
    GET    /{id}                                   — experiment + leaderboard
    DELETE /{id}                                   — delete experiment and model files
    GET    /{id}/models/{model_id}                 — full evaluation of one model
    GET    /{id}/models/{model_id}/download        — download the .joblib pipeline
    POST   /{id}/models/{model_id}/predict         — predict on raw rows
"""

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentDetail,
    ExperimentSummary,
    PredictRequest,
    PredictResponse,
    RecommendationResponse,
    TrainedModelDetail,
)
from app.services.experiment_service import ExperimentService

router = APIRouter()


@router.get("/recommend", response_model=RecommendationResponse)
async def recommend(
    dataset_id: uuid.UUID,
    target_column: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detect the task type for a target column and recommend algorithms."""
    return await ExperimentService(db).recommend(dataset_id, target_column, current_user.id)


@router.post("/", response_model=ExperimentDetail, status_code=201)
async def create_experiment(
    body: ExperimentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Train the selected algorithms, evaluate them on a held-out split and rank them."""
    result = await ExperimentService(db).create_experiment(current_user.id, body)
    await db.commit()
    return result


@router.get("/", response_model=list[ExperimentSummary])
async def list_experiments(
    dataset_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the user's experiments, optionally filtered to one dataset."""
    return await ExperimentService(db).list_experiments(current_user.id, dataset_id)


@router.get("/{experiment_id}", response_model=ExperimentDetail)
async def get_experiment(
    experiment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Experiment configuration, data summary and model leaderboard."""
    return await ExperimentService(db).get_experiment(experiment_id, current_user.id)


@router.delete("/{experiment_id}", status_code=204)
async def delete_experiment(
    experiment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an experiment, its trained models and their files."""
    await ExperimentService(db).delete_experiment(experiment_id, current_user.id)
    await db.commit()


@router.get("/{experiment_id}/models/{model_id}", response_model=TrainedModelDetail)
async def get_model(
    experiment_id: uuid.UUID,
    model_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full evaluation of one trained model: metrics, curves, confusion matrix, importance."""
    return await ExperimentService(db).get_model(experiment_id, model_id, current_user.id)


@router.get("/{experiment_id}/models/{model_id}/download")
async def download_model(
    experiment_id: uuid.UUID,
    model_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the trained scikit-learn pipeline as a .joblib file."""
    path, filename = await ExperimentService(db).get_artifact_path(experiment_id, model_id, current_user.id)
    return FileResponse(path=path, filename=filename, media_type="application/octet-stream")


@router.post("/{experiment_id}/models/{model_id}/predict", response_model=PredictResponse)
async def predict(
    experiment_id: uuid.UUID,
    model_id: uuid.UUID,
    body: PredictRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the saved model on raw input rows (keys = original column names)."""
    return await ExperimentService(db).predict(experiment_id, model_id, current_user.id, body.rows)
