"""Security utilities for password hashing and JWT token management.

Uses bcrypt directly (not through passlib) for Python 3.13 + bcrypt 5.x
compatibility, and python-jose for JWT operations.

Every token carries a ``type`` claim (``access``, ``refresh`` or ``reset``)
and each verifier accepts only its own type, so a refresh or reset token can
never be used as a bearer token for the API.
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_RESET = "reset"


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt.

    Args:
        plain_password: The raw password string to hash.

    Returns:
        The bcrypt-hashed password string.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash.

    Args:
        plain_password: The raw password string to verify.
        hashed_password: The stored bcrypt hash to compare against.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def _create_token(data: dict, token_type: str, expires_delta: timedelta) -> str:
    """Encode a signed JWT with the given type claim and lifetime."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update(
        {"exp": expire, "type": token_type, "jti": str(uuid.uuid4())}
    )
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str, expected_type: str) -> dict | None:
    """Decode a JWT and return its payload only if the type claim matches.

    Returns:
        The payload dict, or None if the signature/expiry is invalid or the
        token is of a different type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Payload dictionary to encode in the token.
        expires_delta: Optional custom expiration timedelta.
            Defaults to ACCESS_TOKEN_EXPIRE_MINUTES from settings.

    Returns:
        Encoded JWT token string.
    """
    return _create_token(
        data,
        TOKEN_TYPE_ACCESS,
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(data: dict) -> str:
    """Create a signed JWT refresh token with longer expiry.

    Args:
        data: Payload dictionary to encode in the token.

    Returns:
        Encoded JWT refresh token string.
    """
    return _create_token(
        data,
        TOKEN_TYPE_REFRESH,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def verify_access_token(token: str) -> dict | None:
    """Decode and verify a JWT access token.

    Refresh and reset tokens are rejected here.

    Args:
        token: The JWT token string to decode.

    Returns:
        The decoded payload dictionary, or None if verification fails.
    """
    return _decode_token(token, TOKEN_TYPE_ACCESS)


def verify_refresh_token(token: str) -> dict | None:
    """Decode and verify a JWT refresh token.

    Args:
        token: The refresh token string to decode.

    Returns:
        The decoded payload dictionary, or None if verification fails.
    """
    return _decode_token(token, TOKEN_TYPE_REFRESH)


def create_reset_token(email: str) -> str:
    """Create a short-lived signed password reset token (15 mins)."""
    return _create_token(
        {"sub": email},
        TOKEN_TYPE_RESET,
        timedelta(minutes=15),
    )


def verify_reset_token(token: str) -> str | None:
    """Verify reset token and return email if valid."""
    payload = _decode_token(token, TOKEN_TYPE_RESET)
    if payload is None:
        return None
    return payload.get("sub")
