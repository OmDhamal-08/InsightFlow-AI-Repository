"""Profiling API endpoints.

Routes:
    POST /datasets/{id}/profile — Run/compute dataset profiling
    GET  /datasets/{id}/profile — Retrieve profiling results
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.profiling import ProfilingResultRead
from app.services.profiling_service import ProfilingService

router = APIRouter()


@router.post("/{dataset_id}/profile", response_model=ProfilingResultRead, status_code=201)
async def run_profiling(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run/re-run profiling on an uploaded dataset.

    Loads the dataset from disk, analyzes column types, computes descriptive
    statistics, uniqueness, null values, and duplicates. Saves results and
    updates dataset status to 'profiled'.
    """
    service = ProfilingService(db)
    result = await service.run_profiling(dataset_id, current_user.id)
    await db.commit()
    return result


@router.get("/{dataset_id}/profile", response_model=ProfilingResultRead)
async def get_profiling(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the profiling result for a dataset."""
    service = ProfilingService(db)
    return await service.get_profiling(dataset_id, current_user.id)
