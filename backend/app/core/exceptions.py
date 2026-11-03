"""Custom exception classes and global FastAPI exception handler.

Provides a hierarchy of application exceptions that map cleanly
to HTTP status codes, plus a handler to convert them into JSON responses.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base application exception.

    All custom exceptions should inherit from this class so they
    can be caught by the global exception handler.

    Attributes:
        status_code: HTTP status code to return.
        detail: Human-readable error description.
        headers: Optional extra response headers.
    """

    def __init__(
        self,
        status_code: int = 500,
        detail: str = "Internal server error",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


class NotFoundException(AppException):
    """Raised when a requested resource is not found (HTTP 404)."""

    def __init__(
        self,
        detail: str = "Resource not found",
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=404, detail=detail, headers=headers)


class UnauthorizedException(AppException):
    """Raised when authentication is required but missing or invalid (HTTP 401)."""

    def __init__(
        self,
        detail: str = "Not authenticated",
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            status_code=401,
            detail=detail,
            headers=headers or {"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(AppException):
    """Raised when the user lacks permission for the requested action (HTTP 403)."""

    def __init__(
        self,
        detail: str = "Permission denied",
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=403, detail=detail, headers=headers)


class BadRequestException(AppException):
    """Raised when the request payload is malformed or invalid (HTTP 400)."""

    def __init__(
        self,
        detail: str = "Bad request",
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=400, detail=detail, headers=headers)


class ConflictException(AppException):
    """Raised when the request conflicts with existing state (HTTP 409)."""

    def __init__(
        self,
        detail: str = "Resource conflict",
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=409, detail=detail, headers=headers)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Global handler that converts AppException subclasses into JSON responses.

    Registered with FastAPI via ``app.add_exception_handler``.

    Args:
        request: The incoming HTTP request.
        exc: The raised AppException instance.

    Returns:
        A JSONResponse with the appropriate status code and error detail.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler: log the traceback and return a JSON 500.

    Without this, an unexpected error returns plain text (or drops the
    connection), and the frontend can't show a useful message.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on the server. The error has been logged."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app instance.

    Args:
        app: The FastAPI application to register handlers on.
    """
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
