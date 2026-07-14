"""Quality analysis API endpoints.

Routes:
    POST /datasets/{id}/quality — Run/compute dataset quality analysis
    GET  /datasets/{id}/quality — Retrieve data quality results
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.quality import QualityResultRead
from app.services.quality_service import QualityService

router = APIRouter()


@router.post("/{dataset_id}/quality", response_model=QualityResultRead, status_code=201)
async def run_quality_analysis(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run/re-run data quality analysis on an uploaded dataset.

    Calculates a multi-dimensional quality index score (Completeness, Uniqueness,
    Outlier-free, Distribution, Independence) and generates actionable recommendations
    mapped directly to preprocessing actions.
    """
    service = QualityService(db)
    result = await service.run_quality_analysis(dataset_id, current_user.id)
    await db.commit()
    return result


@router.get("/{dataset_id}/quality", response_model=QualityResultRead)
async def get_quality_analysis(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the data quality results for a dataset."""
    service = QualityService(db)
    return await service.get_quality_analysis(dataset_id, current_user.id)
