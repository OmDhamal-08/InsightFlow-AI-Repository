"""FastAPI application entry point.

Builds the app: middleware, exception handlers, static files, the JSON API
routers under /api/v1 and the HTML page routes.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import DEFAULT_SECRET_KEY, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import setup_logging
from app.routers import (
    auth,
    dashboard,
    datasets,
    eda,
    experiments,
    features,
    pages,
    preprocessing,
    profiling,
    quality,
    users,
)

settings = get_settings()
logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATIC_DIR = os.path.join(PROJECT_DIR, "frontend", "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("%s v%s starting", settings.APP_NAME, settings.APP_VERSION)
    if settings.SECRET_KEY == DEFAULT_SECRET_KEY and not settings.DEBUG:
        logger.warning("SECRET_KEY is still the default value. Set a real one in .env before deploying.")
    yield
    logger.info("%s shutting down", settings.APP_NAME)


app = FastAPI(
    title="AutoML BI Platform API",
    description=(
        "Dataset upload, profiling, data quality scoring, preprocessing, EDA, "
        "feature engineering, AutoML training and model evaluation."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.exception_handler(StarletteHTTPException)
async def not_found_handler(request: Request, exc: StarletteHTTPException):
    # Browsers get the HTML 404 page; API clients keep getting JSON.
    if exc.status_code == 404 and not request.url.path.startswith("/api"):
        return pages.templates.TemplateResponse(
            request, "errors/404.html", {"title": "Not Found"}, status_code=404
        )
    return await http_exception_handler(request, exc)


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

API = "/api/v1"
app.include_router(auth.router, prefix=f"{API}/auth", tags=["Auth"])
app.include_router(users.router, prefix=f"{API}/users", tags=["Users"])
app.include_router(dashboard.router, prefix=f"{API}/dashboard", tags=["Dashboard"])

# All dataset-scoped features live under /datasets/{id}/...
for module in (datasets, profiling, quality, preprocessing, eda, features):
    app.include_router(module.router, prefix=f"{API}/datasets", tags=["Datasets"])

app.include_router(experiments.router, prefix=f"{API}/experiments", tags=["AutoML"])
app.include_router(pages.router)


@app.get(f"{API}/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
