"""Business logic for authentication workflows.

Orchestrates repository calls, password hashing, and JWT creation.
This layer contains NO database queries — those live in UserRepository.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_access_token,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)
settings = get_settings()


class AuthService:
    """Handles registration, login, token refresh, and logout."""

    def __init__(self, db: AsyncSession) -> None:
        self.repo = UserRepository(db)

    async def register_user(
        self,
        email: str,
        username: str,
        password: str,
        full_name: str | None = None,
    ) -> User:
        """Register a new user account.

        Validates uniqueness of email and username, hashes the password,
        and creates the user with an empty profile.

        Raises:
            ConflictException: If email or username already exists.
        """
        # Check for existing email
        if await self.repo.get_by_email(email):
            raise ConflictException(detail="Email is already registered")

        # Check for existing username
        if await self.repo.get_by_username(username):
            raise ConflictException(detail="Username is already taken")

        hashed = hash_password(password)
        user = await self.repo.create_user(
            email=email,
            username=username,
            hashed_password=hashed,
            full_name=full_name,
        )
        logger.info("New user registered: %s (%s)", username, email)
        return user

    async def authenticate_user(
        self, username_or_email: str, password: str
    ) -> tuple[str, str]:
        """Verify credentials and return (access_token, refresh_token).

        Raises:
            UnauthorizedException: If credentials are invalid.
        """
        user = await self.repo.get_by_email_or_username(username_or_email)
        if not user:
            raise UnauthorizedException(detail="Invalid credentials")

        if not verify_password(password, user.hashed_password):
            raise UnauthorizedException(detail="Invalid credentials")

        if not user.is_active:
            raise UnauthorizedException(detail="Account is deactivated")

        # Create tokens
        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Persist refresh token in DB for revocation support
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self.repo.save_refresh_token(user.id, refresh_token, expires_at)

        logger.info("User logged in: %s", user.username)
        return access_token, refresh_token

    async def refresh_session(self, refresh_token: str) -> tuple[str, str]:
        """Validate a refresh token and issue a new token pair.

        Implements token rotation: the old refresh token is revoked
        and a new one is issued.

        Raises:
            UnauthorizedException: If refresh token is invalid/expired/revoked.
        """
        # Verify the JWT signature
        payload = verify_access_token(refresh_token)
        if not payload:
            raise UnauthorizedException(detail="Invalid refresh token")

        # Check the token exists and is not revoked in DB
        stored = await self.repo.get_refresh_token(refresh_token)
        if not stored or stored.is_revoked:
            raise UnauthorizedException(detail="Refresh token revoked or not found")

        if stored.expires_at < datetime.now(timezone.utc):
            raise UnauthorizedException(detail="Refresh token expired")

        # Revoke old token (rotation)
        await self.repo.revoke_refresh_token(refresh_token)

        # Issue new pair
        user_id = payload.get("sub")
        username = payload.get("username")
        token_data = {"sub": user_id, "username": username}
        new_access = create_access_token(token_data)
        new_refresh = create_refresh_token(token_data)

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self.repo.save_refresh_token(
            stored.user_id, new_refresh, expires_at
        )

        return new_access, new_refresh

    async def logout_user(self, refresh_token: str) -> None:
        """Revoke the given refresh token (single-session logout)."""
        await self.repo.revoke_refresh_token(refresh_token)
        logger.info("User logged out (token revoked)")
