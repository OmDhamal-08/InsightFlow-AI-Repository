"""Dashboard API endpoints.

Routes:
    GET /summary          — Overview counts (datasets, experiments, trained models, avg quality)
    GET /recent-datasets  — The user's recently uploaded datasets
    GET /notifications    — The user's notifications
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.dataset import Dataset
from app.models.quality import QualityResult
from app.models.user import User
from app.repositories.experiment_repository import ExperimentRepository

router = APIRouter()


@router.get("/summary")
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve summary counts for datasets, experiments, trained models and average data quality."""
    stmt = select(func.count()).select_from(Dataset).where(Dataset.user_id == current_user.id)
    datasets_count = (await db.execute(stmt)).scalar() or 0

    experiment_repo = ExperimentRepository(db)
    models_count = await experiment_repo.count_trained_models(current_user.id)
    experiments_count = await experiment_repo.count_experiments(current_user.id)

    quality_stmt = (
        select(func.avg(QualityResult.quality_score))
        .join(Dataset, QualityResult.dataset_id == Dataset.id)
        .where(Dataset.user_id == current_user.id)
    )
    avg_quality = (await db.execute(quality_stmt)).scalar()

    return {
        "datasets_count": datasets_count,
        "models_count": models_count,
        "experiments_count": experiments_count,
        "data_quality_score": round(float(avg_quality), 1) if avg_quality is not None else None,
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
            "name": ds.name,
            "file_size": ds.file_size,
            "row_count": ds.row_count,
            "column_count": ds.column_count,
            "status": ds.status,
            "created_at": ds.created_at.isoformat(),
        }
        for ds in datasets
    ]


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
