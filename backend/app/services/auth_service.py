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
    verify_password,
    verify_refresh_token,
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

        access_token, refresh_token = await self._issue_tokens(user)
        logger.info("User logged in: %s", user.username)
        return access_token, refresh_token

    async def _issue_tokens(self, user: User) -> tuple[str, str]:
        """Create an access/refresh pair and store the refresh token for revocation."""
        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await self.repo.save_refresh_token(user.id, refresh_token, expires_at)
        return access_token, refresh_token

    async def change_password(self, user: User, current_password: str, new_password: str) -> tuple[str, str]:
        """Change the password of a logged-in user.

        Every existing session is revoked (other devices are logged out) and a
        fresh token pair is returned so the current browser stays signed in.

        Raises:
            BadRequestException: Current password is wrong or unchanged.
        """
        if not verify_password(current_password, user.hashed_password):
            raise BadRequestException(detail="Current password is incorrect")
        if verify_password(new_password, user.hashed_password):
            raise BadRequestException(detail="New password must be different from the current one")

        await self.repo.update_password(user, hash_password(new_password))
        await self.repo.revoke_all_user_tokens(user.id)
        logger.info("Password changed for user: %s", user.username)
        return await self._issue_tokens(user)

    async def refresh_session(self, refresh_token: str) -> tuple[str, str]:
        """Validate a refresh token and issue a new token pair.

        Implements token rotation: the old refresh token is revoked
        and a new one is issued.

        Raises:
            UnauthorizedException: If refresh token is invalid/expired/revoked.
        """
        # Verify the JWT signature and that it really is a refresh token
        payload = verify_refresh_token(refresh_token)
        if not payload:
            raise UnauthorizedException(detail="Invalid refresh token")

        # Check the token exists and is not revoked in DB
        stored = await self.repo.get_refresh_token(refresh_token)
        if not stored or stored.is_revoked:
            raise UnauthorizedException(detail="Refresh token revoked or not found")

        # PostgreSQL returns timezone-aware datetimes; SQLite (used in tests) returns naive ones.
        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
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

    async def request_password_reset(self, email: str) -> str | None:
        """Generate a password reset token for the given email address.

        Returns:
            The reset token, or None if no account uses this email. Callers
            must not reveal which case happened to the client.
        """
        user = await self.repo.get_by_email(email)
        if not user:
            return None

        from app.core.security import create_reset_token
        return create_reset_token(user.email)

    async def reset_password_with_token(self, token: str, new_password: str) -> None:
        """Reset user password using a verified reset token.

        Raises:
            BadRequestException: If token is invalid or expired.
        """
        from app.core.security import verify_reset_token, hash_password
        email = verify_reset_token(token)
        if not email:
            raise BadRequestException(detail="Invalid or expired reset token")

        user = await self.repo.get_by_email(email)
        if not user:
            raise BadRequestException(detail="User not found")

        # Hash and update password
        hashed = hash_password(new_password)
        await self.repo.update_password(user, hashed)

        # Revoke all user sessions for safety on password change
        await self.repo.revoke_all_user_tokens(user.id)
        logger.info("Password successfully reset for user: %s", user.username)

