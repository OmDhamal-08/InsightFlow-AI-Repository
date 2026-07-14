"""Dashboard API endpoints.

Routes:
    GET /summary          — Get overview metrics counts (datasets, models, reports, quality)
    GET /recent-datasets  — Get user's recently uploaded datasets
    GET /recent-reports   — Get user's recently generated reports
    GET /notifications    — Get user's notifications
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.dataset import Dataset
from app.models.user import User

router = APIRouter()


@router.get("/summary")
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve summary counts for datasets, models, reports, and data quality.

    Queries the datasets table for a real count; models/reports return 0
    until those phases are implemented.
    """
    # Real dataset count
    stmt = select(func.count()).where(Dataset.user_id == current_user.id)
    result = await db.execute(stmt)
    datasets_count = result.scalar() or 0

    return {
        "datasets_count": datasets_count,
        "models_count": 0,          # Phase 10
        "reports_count": 0,          # Phase 16
        "data_quality_score": None,  # Phase 6
    }


@router.get("/recent-datasets")
async def get_recent_datasets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the user's 5 most recently uploaded datasets."""
    stmt = (
        select(Dataset)
        .where(Dataset.user_id == current_user.id)
        .order_by(Dataset.created_at.desc())
        .limit(5)
    )
    result = await db.execute(stmt)
    datasets = result.scalars().all()

    return [
        {
            "id": str(ds.id),
            "filename": ds.name,
            "size_bytes": ds.file_size,
            "rows_count": ds.row_count,
            "created_at": ds.created_at.isoformat(),
        }
        for ds in datasets
    ]


@router.get("/recent-reports")
async def get_recent_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a list of the user's recently generated reports."""
    # Placeholder for Phase 16 (Report Generator)
    return []


@router.get("/notifications")
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all notifications for the current user."""
    return [
        {
            "id": "welcome-notification",
            "title": "Welcome to AI BI Platform",
            "message": "Upload your first CSV or Excel dataset to begin automated profiling and ML model training.",
            "is_read": False,
            "created_at": current_user.created_at.isoformat(),
        }
    ]
