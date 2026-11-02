"""Pydantic schemas for authentication requests and responses."""

from pydantic import BaseModel, EmailStr, Field, field_validator

SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"


def check_password_strength(v: str) -> str:
    """Require upper- and lowercase letters, a digit and a special character."""
    if not any(c.isupper() for c in v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one digit")
    if not any(c in SPECIAL_CHARS for c in v):
        raise ValueError("Password must contain at least one special character")
    return v


class UserRegister(BaseModel):
    """Registration request payload."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Ensure password has uppercase, lowercase, digit, and special char."""
        return check_password_strength(v)


class UserLogin(BaseModel):
    """Login request payload. Accepts email or username."""

    username_or_email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """JWT token response returned on login/refresh."""

    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class ForgotPasswordRequest(BaseModel):
    """Payload to request password reset token."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Payload to reset password using token."""

    token: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Ensure password has uppercase, lowercase, digit, and special char."""
        return check_password_strength(v)



class PasswordChangeRequest(BaseModel):
    """Change password while logged in."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return check_password_strength(v)
