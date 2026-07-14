"""Authentication API endpoints.

Routes:
    POST /register  — Create a new user account
    POST /login     — Authenticate and receive JWT tokens
    POST /refresh   — Rotate refresh token and get new access token
    POST /logout    — Revoke refresh token
    GET  /me        — Get current authenticated user info
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    MessageResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from app.schemas.user import UserWithProfile
from app.services.auth_service import AuthService

router = APIRouter()
settings = get_settings()

# Cookie settings for refresh token
_COOKIE_KEY = "refresh_token"
_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # seconds


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set the refresh token as an HTTP-only secure cookie."""
    response.set_cookie(
        key=_COOKIE_KEY,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True in production with HTTPS
        path="/api/v1/auth",  # Restrict cookie to auth endpoints
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Delete the refresh token cookie."""
    response.delete_cookie(key=_COOKIE_KEY, path="/api/v1/auth")


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: UserRegister,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user and return tokens to auto-login."""
    service = AuthService(db)
    user = await service.register_user(
        email=body.email,
        username=body.username,
        password=body.password,
        full_name=body.full_name,
    )
    # Auto-login after registration
    access_token, refresh_token = await service.authenticate_user(
        body.email, body.password
    )
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return access token + refresh cookie."""
    service = AuthService(db)
    access_token, refresh_token = await service.authenticate_user(
        body.username_or_email, body.password
    )
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    # Read refresh token from cookie
    refresh_token: str = Depends(lambda request: request.cookies.get(_COOKIE_KEY, "")),
) -> TokenResponse:
    """Rotate refresh token and issue a new access token."""
    from app.core.exceptions import UnauthorizedException

    if not refresh_token:
        raise UnauthorizedException(detail="Refresh token not found")

    service = AuthService(db)
    new_access, new_refresh = await service.refresh_session(refresh_token)
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=new_access)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str = Depends(lambda request: request.cookies.get(_COOKIE_KEY, "")),
) -> MessageResponse:
    """Revoke refresh token and clear cookie."""
    if refresh_token:
        service = AuthService(db)
        await service.logout_user(refresh_token)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserWithProfile)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserWithProfile:
    """Return the currently authenticated user with profile."""
    return UserWithProfile.model_validate(current_user)
