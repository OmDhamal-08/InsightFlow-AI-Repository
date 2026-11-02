"""Exploratory Data Analysis (EDA) API endpoints.

Routes:
    POST /datasets/{id}/eda/generate — Pre-calculate overview summary charts
    POST /datasets/{id}/eda/custom   — Dynamically compute custom plots (normality, scatters)
    GET  /datasets/{id}/eda          — Retrieve summary charts list
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.eda import EdaCustomRequest, EdaResultRead
from app.services.eda_service import EdaService

router = APIRouter()


@router.post("/{dataset_id}/eda/generate", response_model=list[EdaResultRead], status_code=201)
async def run_summary_eda(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Auto-generate and persist default summary charts (heatmaps, null counts, distributions) for a dataset."""
    service = EdaService(db)
    result = await service.run_summary_eda(dataset_id, current_user.id)
    await db.commit()
    return result


@router.post("/{dataset_id}/eda/custom", response_model=dict)
async def get_custom_plot(
    dataset_id: uuid.UUID,
    req: EdaCustomRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dynamically calculate statistical coordinates for custom explorations (normality, scatters, boxplots).

    These coordinates are calculated on the fly and are not stored in the database.
    """
    service = EdaService(db)
    return await service.get_custom_plot(
        dataset_id=dataset_id,
        user_id=current_user.id,
        chart_type=req.chart_type,
        columns=req.columns,
    )


@router.get("/{dataset_id}/eda", response_model=list[EdaResultRead])
async def list_summary_eda(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve pre-calculated overview summary charts for a dataset."""
    service = EdaService(db)
    return await service.list_summary_eda(dataset_id, current_user.id)


@router.get("/{dataset_id}/eda/bivariate", response_model=dict)
async def get_bivariate_analysis(
    dataset_id: uuid.UUID,
    target_column: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute target-aware bivariate statistical associations and chart data.

    Returns Pearson/Spearman, ANOVA, Kruskal-Wallis, Chi-Square/Cramér's V
    tests plus bivariate chart coordinates for the specified target column.
    """
    service = EdaService(db)
    return await service.get_bivariate_analysis(dataset_id, current_user.id, target_column)

