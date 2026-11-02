"""Authentication API endpoints.

Routes:
    POST /register  — Create a new user account
    POST /login     — Authenticate and receive JWT tokens
    POST /refresh   — Rotate refresh token and get new access token
    POST /logout    — Revoke refresh token
    GET  /me        — Get current authenticated user info
    POST /change-password — Change password (logged in), revokes other sessions
    POST /forgot-password, /reset-password — Password reset by token
"""

from fastapi import APIRouter, Depends, Request, Response
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
    ForgotPasswordRequest,
    PasswordChangeRequest,
    ResetPasswordRequest,
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


def _get_refresh_cookie(request: Request) -> str:
    """Read the refresh token from the cookie (empty string if absent).

    Must be a typed function: an untyped ``lambda request: ...`` dependency is
    treated by FastAPI as a required query parameter named ``request``.
    """
    return request.cookies.get(_COOKIE_KEY, "")


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
    refresh_token: str = Depends(_get_refresh_cookie),
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
    refresh_token: str = Depends(_get_refresh_cookie),
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


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Start a password reset for the given email.

    The response is the same whether or not the email is registered, so the
    endpoint cannot be used to discover accounts.

    No email delivery is configured yet. While ``DEBUG`` is on (local
    development), the reset link is returned in the message so the reset page
    can be exercised end to end. With ``DEBUG`` off, the token is never
    returned to the client.
    """
    service = AuthService(db)
    token = await service.request_password_reset(body.email)
    if settings.DEBUG and token:
        return MessageResponse(
            message=f"Reset token generated successfully. Click link to reset: /reset-password?token={token}"
        )
    return MessageResponse(
        message="If an account exists for that email, a password reset link has been generated."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Reset user password using token."""
    service = AuthService(db)
    await service.reset_password_with_token(body.token, body.new_password)
    return MessageResponse(message="Password has been reset successfully")


@router.post("/change-password", response_model=TokenResponse)
async def change_password(
    body: PasswordChangeRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Change the current user's password and rotate their session tokens."""
    service = AuthService(db)
    access_token, refresh_token = await service.change_password(
        current_user, body.current_password, body.new_password
    )
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)
