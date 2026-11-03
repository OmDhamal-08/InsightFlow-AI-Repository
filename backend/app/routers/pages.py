"""Server-rendered HTML pages.

Every page is a Jinja2 template. The pages themselves hold no data; the
JavaScript on each page calls the JSON API under /api/v1 with the user's token.
"""

import os

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "frontend",
    "templates",
)

templates = Jinja2Templates(directory=TEMPLATES_DIR)
router = APIRouter(include_in_schema=False)


def render(request: Request, template: str, title: str, active_page: str, **context):
    return templates.TemplateResponse(
        request,
        f"pages/{template}",
        {"title": title, "active_page": active_page, **context},
    )


# Templates link to pages with url_for("<function name>"), e.g. url_for("login_page"),
# so renaming one of these functions breaks those links.

# Public pages

@router.get("/")
async def home_page(request: Request):
    return render(request, "home.html", "Home", "home")


@router.get("/login")
async def login_page(request: Request):
    return render(request, "login.html", "Login", "login")


@router.get("/register")
async def register_page(request: Request):
    return render(request, "register.html", "Register", "register")


@router.get("/forgot-password")
async def forgot_password_page(request: Request):
    return render(request, "forgot_password.html", "Forgot Password", "forgot-password")


@router.get("/reset-password")
async def reset_password_page(request: Request):
    return render(request, "reset_password.html", "Reset Password", "reset-password")


@router.get("/terms")
async def terms_page(request: Request):
    return render(request, "terms.html", "Terms of Service", "terms")


@router.get("/privacy")
async def privacy_page(request: Request):
    return render(request, "privacy.html", "Privacy Policy", "privacy")


# App pages (the JS on these pages redirects to /login if there is no token)

@router.get("/dashboard")
async def dashboard_page(request: Request):
    return render(request, "dashboard.html", "Dashboard", "dashboard")


@router.get("/upload")
async def upload_page(request: Request):
    return render(request, "upload.html", "Upload", "upload")


@router.get("/settings")
async def settings_page(request: Request):
    return render(request, "settings.html", "Settings", "settings")


# Per-dataset pages share the dataset sub-navigation, so they also pass active_subpage.
DATASET_PAGES = {
    "profile": ("profiling.html", "Dataset Profiling"),
    "quality": ("quality.html", "Data Quality"),
    "preprocess": ("preprocessing.html", "Preprocessing"),
    "eda": ("eda.html", "Exploratory Data Analysis"),
    "features": ("features.html", "Feature Engineering"),
}


@router.get("/datasets/{dataset_id}/{subpage}")
async def dataset_page(request: Request, dataset_id: str, subpage: str):
    if subpage not in DATASET_PAGES:
        return templates.TemplateResponse(request, "errors/404.html", {"title": "Not Found"}, status_code=404)
    template, title = DATASET_PAGES[subpage]
    return render(
        request, template, title, "upload",
        active_subpage=subpage, dataset_id=dataset_id,
    )


@router.get("/experiments")
async def experiments_page(request: Request):
    return render(
        request, "experiments.html", "AutoML Experiments", "experiments",
        dataset_id=request.query_params.get("dataset_id", ""),
    )


@router.get("/experiments/{experiment_id}")
async def experiment_detail_page(request: Request, experiment_id: str):
    return render(
        request, "experiment_detail.html", "Model Evaluation", "experiments",
        experiment_id=experiment_id,
    )
