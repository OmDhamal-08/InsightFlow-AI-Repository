"""Data access layer for User, Profile, and RefreshToken models.

All database queries related to authentication are centralised here,
keeping the service layer free of raw SQLAlchemy calls.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import Profile, RefreshToken, User


class UserRepository:
    """CRUD operations for users and related entities."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── User queries ─────────────────────────────────────────────

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch a user by primary key, eagerly loading profile."""
        stmt = (
            select(User)
            .options(selectinload(User.profile))
            .where(User.id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by email address."""
        stmt = select(User).where(User.email == email.lower())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Fetch a user by username."""
        stmt = select(User).where(User.username == username.lower())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email_or_username(self, identifier: str) -> User | None:
        """Fetch a user by email OR username (for login flexibility)."""
        identifier_lower = identifier.lower()
        stmt = (
            select(User)
            .options(selectinload(User.profile))
            .where(
                (User.email == identifier_lower)
                | (User.username == identifier_lower)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        username: str,
        hashed_password: str,
        full_name: str | None = None,
    ) -> User:
        """Create a new user with an empty profile.

        Args:
            email: Validated email address.
            username: Unique username.
            hashed_password: bcrypt-hashed password.
            full_name: Optional display name.

        Returns:
            The newly created User with its Profile attached.
        """
        user = User(
            email=email.lower(),
            username=username.lower(),
            hashed_password=hashed_password,
        )
        # Create an empty profile automatically
        profile = Profile(user=user, full_name=full_name)
        self.db.add(user)
        self.db.add(profile)
        await self.db.flush()  # Assign IDs without committing
        return user

    # ── Refresh token queries ────────────────────────────────────

    async def save_refresh_token(
        self, user_id: uuid.UUID, token: str, expires_at: datetime
    ) -> RefreshToken:
        """Store a new refresh token in the database."""
        rt = RefreshToken(
            user_id=user_id, token=token, expires_at=expires_at
        )
        self.db.add(rt)
        await self.db.flush()
        return rt

    async def get_refresh_token(self, token: str) -> RefreshToken | None:
        """Fetch a refresh token record by its token string."""
        stmt = select(RefreshToken).where(RefreshToken.token == token)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, token: str) -> None:
        """Mark a refresh token as revoked."""
        rt = await self.get_refresh_token(token)
        if rt:
            rt.is_revoked = True
            await self.db.flush()

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> None:
        """Revoke every refresh token for a given user (force logout)."""
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
        result = await self.db.execute(stmt)
        for rt in result.scalars().all():
            rt.is_revoked = True
        await self.db.flush()

    # ── Profile queries ──────────────────────────────────────────

    async def update_profile(
        self, user_id: uuid.UUID, **fields: str | None
    ) -> Profile | None:
        """Update profile fields for a user.

        Only non-None values in ``fields`` are applied.
        """
        user = await self.get_by_id(user_id)
        if not user or not user.profile:
            return None
        for key, value in fields.items():
            if hasattr(user.profile, key) and value is not None:
                setattr(user.profile, key, value)
        await self.db.flush()
        return user.profile
