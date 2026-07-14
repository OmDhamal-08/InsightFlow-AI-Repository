"""User profile management endpoints.

Routes:
    GET  /profile  — Get current user's profile
    PUT  /profile  — Update current user's profile
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import ProfileRead, ProfileUpdate

router = APIRouter()


@router.get("/profile", response_model=ProfileRead)
async def get_profile(
    current_user: User = Depends(get_current_user),
) -> ProfileRead:
    """Return the current user's profile."""
    return ProfileRead.model_validate(current_user.profile)


@router.put("/profile", response_model=ProfileRead)
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileRead:
    """Update the current user's profile fields."""
    repo = UserRepository(db)
    updated = await repo.update_profile(
        user_id=current_user.id,
        **body.model_dump(exclude_unset=True),
    )
    return ProfileRead.model_validate(updated)
