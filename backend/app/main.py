"""FastAPI application entry point for the AI-Powered BI Platform.

Creates the FastAPI app instance, registers middleware, exception handlers,
routers, static-file mounts, and Jinja2 template routes.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import DEFAULT_SECRET_KEY, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import setup_logging

settings = get_settings()
logger = logging.getLogger(__name__)

# ── Resolve directory paths relative to this file ──────────────────────
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)
_FRONTEND_DIR = os.path.join(_PROJECT_DIR, "frontend")
_STATIC_DIR = os.path.join(_FRONTEND_DIR, "static")
_TEMPLATES_DIR = os.path.join(_FRONTEND_DIR, "templates")

# ── Jinja2 templates ──────────────────────────────────────────────────
templates = Jinja2Templates(directory=_TEMPLATES_DIR) if os.path.isdir(_TEMPLATES_DIR) else None


# ── Lifespan (startup / shutdown) ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events.

    Startup:
        - Configure logging.
        - Log application start message.

    Shutdown:
        - Log graceful-shutdown message.
    """
    # ── Startup ───────────────────────────────────────────────────
    setup_logging()
    logger.info(
        "%s v%s starting up…",
        settings.APP_NAME,
        settings.APP_VERSION,
    )
    if settings.SECRET_KEY == DEFAULT_SECRET_KEY and not settings.DEBUG:
        logger.warning(
            "SECRET_KEY is the default placeholder. Set a strong SECRET_KEY in .env before deploying "
            "(e.g. python -c \"import secrets; print(secrets.token_hex(32))\")."
        )
    yield
    # ── Shutdown ──────────────────────────────────────────────────
    logger.info("%s shutting down…", settings.APP_NAME)


# ── FastAPI application instance ──────────────────────────────────────
app = FastAPI(
    title="AI BI Platform API",
    description=(
        "Backend API for the AI-Powered Business Intelligence Platform: dataset upload, "
        "profiling, data quality scoring, preprocessing, EDA, feature engineering, "
        "AutoML training and model evaluation."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS middleware ───────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ───────────────────────────────────────────────
register_exception_handlers(app)

# ── Static files (only if the directory exists) ───────────────────────
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# ══════════════════════════════════════════════════════════════════════
# API Router Includes
# ══════════════════════════════════════════════════════════════════════

# Phase 2: Authentication & User Management
from app.routers import auth as auth_router
from app.routers import users as users_router
from app.routers import dashboard as dashboard_router
app.include_router(auth_router.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users_router.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(dashboard_router.router, prefix="/api/v1/dashboard", tags=["Dashboard"])

# Phases 4–9: Dataset upload, profiling, quality, preprocessing, EDA, feature engineering
from app.routers import datasets as datasets_router
from app.routers import profiling as profiling_router
from app.routers import quality as quality_router
from app.routers import preprocessing as preprocessing_router
from app.routers import eda as eda_router
from app.routers import features as features_router
app.include_router(datasets_router.router, prefix="/api/v1/datasets", tags=["Datasets"])
app.include_router(profiling_router.router, prefix="/api/v1/datasets", tags=["Datasets"])
app.include_router(quality_router.router, prefix="/api/v1/datasets", tags=["Datasets"])
app.include_router(preprocessing_router.router, prefix="/api/v1/datasets", tags=["Datasets"])
app.include_router(eda_router.router, prefix="/api/v1/datasets", tags=["Datasets"])
app.include_router(features_router.router, prefix="/api/v1/datasets", tags=["Datasets"])

# Phases 10–11: AutoML training and model evaluation
from app.routers import experiments as experiments_router
app.include_router(experiments_router.router, prefix="/api/v1/experiments", tags=["AutoML & Evaluation"])


# ══════════════════════════════════════════════════════════════════════
# Core API Endpoints
# ══════════════════════════════════════════════════════════════════════


@app.get(
    "/api/v1/health",
    tags=["Health"],
    summary="Health check",
    response_model=None,
)
async def health_check() -> dict:
    """Return the current health status of the API.

    Returns:
        A JSON object with ``status``, ``version``, and ``timestamp``.
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
# Frontend Page Routes (Jinja2 Templates)
# ══════════════════════════════════════════════════════════════════════


@app.get("/", tags=["Pages"], include_in_schema=False)
async def home_page(request: Request):
    """Render the home / landing page."""
    if templates is None:
        return JSONResponse(
            content={"message": "Frontend templates not found. API is running at /docs"},
            status_code=200,
        )
    return templates.TemplateResponse(
        request, "pages/home.html", {"title": "Home", "active_page": "home"}
    )


@app.get("/login", tags=["Pages"], include_in_schema=False)
async def login_page(request: Request):
    """Render the login page."""
    if templates is None:
        return JSONResponse(content={"message": "Login page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/login.html", {"title": "Login", "active_page": "login"}
    )


@app.get("/register", tags=["Pages"], include_in_schema=False)
async def register_page(request: Request):
    """Render the registration page."""
    if templates is None:
        return JSONResponse(content={"message": "Register page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/register.html", {"title": "Register", "active_page": "register"}
    )


@app.get("/forgot-password", tags=["Pages"], include_in_schema=False)
async def forgot_password_page(request: Request):
    """Render the forgot password request page."""
    if templates is None:
        return JSONResponse(content={"message": "Forgot password page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/forgot_password.html", {"title": "Forgot Password", "active_page": "forgot-password"}
    )


@app.get("/reset-password", tags=["Pages"], include_in_schema=False)
async def reset_password_page(request: Request):
    """Render the reset password set page."""
    if templates is None:
        return JSONResponse(content={"message": "Reset password page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/reset_password.html", {"title": "Reset Password", "active_page": "reset-password"}
    )


@app.get("/terms", tags=["Pages"], include_in_schema=False)
async def terms_page(request: Request):
    """Render the Terms of Service page."""
    if templates is None:
        return JSONResponse(content={"message": "Terms page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/terms.html", {"title": "Terms of Service", "active_page": "terms"}
    )


@app.get("/privacy", tags=["Pages"], include_in_schema=False)
async def privacy_page(request: Request):
    """Render the Privacy Policy page."""
    if templates is None:
        return JSONResponse(content={"message": "Privacy page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/privacy.html", {"title": "Privacy Policy", "active_page": "privacy"}
    )



@app.get("/dashboard", tags=["Pages"], include_in_schema=False)
async def dashboard_page(request: Request):
    """Render the main dashboard page."""
    if templates is None:
        return JSONResponse(content={"message": "Dashboard page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/dashboard.html", {"title": "Dashboard", "active_page": "dashboard"}
    )


@app.get("/upload", tags=["Pages"], include_in_schema=False)
async def upload_page(request: Request):
    """Render the file upload page."""
    if templates is None:
        return JSONResponse(content={"message": "Upload page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/upload.html", {"title": "Upload", "active_page": "upload"}
    )


@app.get("/settings", tags=["Pages"], include_in_schema=False)
async def settings_page(request: Request):
    """Render the user settings page."""
    if templates is None:
        return JSONResponse(content={"message": "Settings page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/settings.html", {"title": "Settings", "active_page": "settings"}
    )


@app.get("/datasets/{dataset_id}/profile", tags=["Pages"], include_in_schema=False)
async def datasets_profile_page(request: Request, dataset_id: str):
    """Render the dataset profiling results page."""
    if templates is None:
        return JSONResponse(content={"message": "Profiling page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/profiling.html", {
            "title": "Dataset Profiling",
            "active_page": "upload",
            "active_subpage": "profile",
            "dataset_id": dataset_id
        }
    )


@app.get("/datasets/{dataset_id}/quality", tags=["Pages"], include_in_schema=False)
async def datasets_quality_page(request: Request, dataset_id: str):
    """Render the dataset quality analysis results page."""
    if templates is None:
        return JSONResponse(content={"message": "Quality page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/quality.html", {
            "title": "Data Quality Engine",
            "active_page": "upload",
            "active_subpage": "quality",
            "dataset_id": dataset_id
        }
    )


@app.get("/datasets/{dataset_id}/preprocess", tags=["Pages"], include_in_schema=False)
async def datasets_preprocess_page(request: Request, dataset_id: str):
    """Render the dataset smart preprocessing wizard page."""
    if templates is None:
        return JSONResponse(content={"message": "Preprocessing page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/preprocessing.html", {
            "title": "Smart Preprocessing",
            "active_page": "upload",
            "active_subpage": "preprocess",
            "dataset_id": dataset_id
        }
    )


@app.get("/datasets/{dataset_id}/eda", tags=["Pages"], include_in_schema=False)
async def datasets_eda_page(request: Request, dataset_id: str):
    """Render the dataset Exploratory Data Analysis (EDA) dashboard page."""
    if templates is None:
        return JSONResponse(content={"message": "EDA page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/eda.html", {
            "title": "Exploratory Data Analysis",
            "active_page": "upload",
            "active_subpage": "eda",
            "dataset_id": dataset_id
        }
    )


@app.get("/datasets/{dataset_id}/features", tags=["Pages"], include_in_schema=False)
async def datasets_features_page(request: Request, dataset_id: str):
    """Render the dataset feature engineering dashboard page."""
    if templates is None:
        return JSONResponse(content={"message": "Feature engineering page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/features.html", {
            "title": "Feature Engineering",
            "active_page": "upload",
            "active_subpage": "features",
            "dataset_id": dataset_id
        }
    )


@app.get("/experiments", tags=["Pages"], include_in_schema=False)
async def experiments_page(request: Request):
    """Render the AutoML experiments page (create + list)."""
    if templates is None:
        return JSONResponse(content={"message": "Experiments page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/experiments.html", {
            "title": "AutoML Experiments",
            "active_page": "experiments",
            "dataset_id": request.query_params.get("dataset_id", ""),
        }
    )


@app.get("/experiments/{experiment_id}", tags=["Pages"], include_in_schema=False)
async def experiment_detail_page(request: Request, experiment_id: str):
    """Render the model leaderboard and evaluation page for one experiment."""
    if templates is None:
        return JSONResponse(content={"message": "Experiment page — templates not configured"})
    return templates.TemplateResponse(
        request, "pages/experiment_detail.html", {
            "title": "Model Evaluation",
            "active_page": "experiments",
            "experiment_id": experiment_id,
        }
    )
