"""Feature Engineering API endpoints.

Routes:
    POST /datasets/{id}/features/generate — Run preview & register FeatureSet
    GET  /datasets/{id}/features          — List feature sets
    GET  /datasets/{id}/features/{fid}     — Detail of a feature set
    POST /datasets/{id}/features/{fid}/apply — Apply features, write CSV & register Dataset
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.feature import FeatureGenerateRequest, FeaturePreviewResponse, FeatureSetRead
from app.services.feature_service import FeatureService

router = APIRouter()


@router.post("/{dataset_id}/features/generate", status_code=201)
async def generate_feature_set(
    dataset_id: uuid.UUID,
    req: FeatureGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run feature engineering previews and register the engineered FeatureSet configuration."""
    service = FeatureService(db)
    feature_set, preview = await service.generate_feature_set(
        dataset_id=dataset_id,
        user_id=current_user.id,
        name=req.name,
        method=req.method,
        config=req.config,
    )
    await db.commit()
    return {"feature_set": FeatureSetRead.model_validate(feature_set), "preview": preview}


@router.get("/{dataset_id}/features", response_model=list[FeatureSetRead])
async def list_feature_sets(
    dataset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all feature sets created for a dataset."""
    service = FeatureService(db)
    return await service.list_feature_sets(dataset_id, current_user.id)


@router.get("/{dataset_id}/features/{feature_set_id}", response_model=FeatureSetRead)
async def get_feature_set(
    dataset_id: uuid.UUID,
    feature_set_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of a specific feature set."""
    service = FeatureService(db)
    return await service.get_feature_set(dataset_id, feature_set_id, current_user.id)


@router.post("/{dataset_id}/features/{feature_set_id}/apply", response_model=FeatureSetRead)
async def apply_feature_set(
    dataset_id: uuid.UUID,
    feature_set_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute feature engineering transformations, write cleaned CSV to disk, and register it."""
    service = FeatureService(db)
    result = await service.apply_feature_set(dataset_id, feature_set_id, current_user.id)
    await db.commit()
    return result
