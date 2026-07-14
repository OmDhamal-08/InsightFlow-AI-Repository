"""Pydantic schemas for User and Profile read/update operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProfileRead(BaseModel):
    """Public profile information."""

    full_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    company: str | None = None
    role: str | None = None

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    """Fields that can be updated on a profile."""

    full_name: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=1000)
    company: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=100)


class UserRead(BaseModel):
    """Public user information (no password)."""

    id: uuid.UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserWithProfile(BaseModel):
    """User with their profile data — used by /auth/me."""

    id: uuid.UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime
    profile: ProfileRead | None = None

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    """Request body for changing password."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
