"""Shared FastAPI dependencies for dependency injection.

The ``get_current_user`` dependency extracts and validates the JWT
from the ``Authorization: Bearer <token>`` header, then fetches the
corresponding User record from the database.
"""

import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedException
from app.core.security import verify_access_token
from app.database import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository

# HTTP Bearer scheme — extracts token from "Authorization: Bearer ..." header
security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the JWT in the request.

    This dependency:
    1. Reads the ``Authorization: Bearer <token>`` header.
    2. Decodes and verifies the JWT signature and expiry.
    3. Extracts the ``sub`` claim (user ID).
    4. Fetches the User from the database.

    Raises:
        UnauthorizedException: If token is missing, invalid, or the user
            does not exist / is deactivated.
    """
    if credentials is None:
        raise UnauthorizedException(detail="Authentication required")

    payload = verify_access_token(credentials.credentials)
    if payload is None:
        raise UnauthorizedException(detail="Invalid or expired token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException(detail="Invalid token payload")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise UnauthorizedException(detail="Invalid token payload")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise UnauthorizedException(detail="User not found")
    if not user.is_active:
        raise UnauthorizedException(detail="Account is deactivated")

    return user
