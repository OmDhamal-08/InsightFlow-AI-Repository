# AI-Powered Business Intelligence Platform

> **Enterprise-grade, AI-powered BI platform** that takes you from raw CSV/Excel data to actionable intelligence — zero code required.

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green?style=flat-square&logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-blue?style=flat-square&logo=postgresql)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## 🚀 Features

- **📊 Dataset Upload & Profiling** — Upload CSV/Excel, auto-profile columns, stats, and types
- **🔍 Data Quality Engine** — Quality scoring with actionable recommendations
- **🧹 Smart Preprocessing** — AI-recommended transformations with explanations
- **📈 Auto-EDA** — Auto-generated charts with plain-English insights
- **🤖 AutoML Engine** — Automatic model selection, training, and hyperparameter tuning
- **🧠 Explainable AI** — SHAP-based explanations for every prediction
- **📉 Forecasting** — Time-series forecasting with trend and seasonality
- **🔔 Anomaly Detection** — Multi-algorithm anomaly detection with reasons
- **💬 AI Business Assistant** — Natural-language Q&A grounded in your data analysis
- **📋 Report Generator** — Export PDF/Word/HTML reports

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy 2.0, Alembic, PostgreSQL, Pydantic v2 |
| **Frontend** | HTML5, CSS3, JavaScript, Tailwind CSS, Chart.js, Plotly.js |
| **ML/AI** | Scikit-learn, XGBoost, LightGBM, CatBoost, SHAP, Prophet, Optuna |
| **AI Assistant** | OpenAI/OpenRouter, LangChain, FAISS, Sentence-Transformers |
| **DevOps** | Docker, Docker Compose, Nginx, GitHub Actions, AWS EC2 |

---

## 📁 Project Structure

```
auto_ml_pipline/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py             # Application entry point
│   │   ├── config.py           # Settings & environment
│   │   ├── database.py         # Database connection
│   │   ├── routers/            # API route handlers
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # Business logic
│   │   ├── repositories/       # Data access layer
│   │   ├── ml/                 # ML engine implementations
│   │   ├── core/               # Security, logging, exceptions
│   │   └── utils/              # Utility functions
│   ├── alembic/                # Database migrations
│   ├── tests/                  # Test suite
│   ├── requirements.txt        # Python dependencies
│   └── .env.example            # Environment template
├── frontend/
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── base.html           # Base layout
│   │   ├── components/         # Shared UI components
│   │   └── pages/              # Page templates
│   └── static/
│       ├── css/                # Stylesheets
│       ├── js/                 # JavaScript modules
│       └── images/             # Static images
├── storage/                    # Runtime file storage
│   ├── uploads/                # Uploaded datasets
│   ├── models/                 # Trained ML models
│   └── reports/                # Generated reports
├── docs/                       # Documentation
├── docker-compose.yml          # Docker orchestration
└── README.md                   # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **PostgreSQL 14+**
- **Git**

### 1. Clone the Repository

```bash
git clone <repository-url>
cd auto_ml_pipline
```

### 2. Set Up the Backend

```bash
# Create virtual environment
cd backend
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your settings (especially DATABASE_URL and SECRET_KEY)
```

### 4. Set Up the Database

```bash
# Create the PostgreSQL database
createdb ai_bi_platform

# Run database migrations
alembic upgrade head
```

### 5. Run the Application

```bash
# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Open in Browser

- **Application**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **API Docs (ReDoc)**: http://localhost:8000/redoc

---

## 🔧 Environment Variables

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Application name | AI BI Platform |
| `APP_VERSION` | Application version | 0.1.0 |
| `DEBUG` | Debug mode | true |
| `DATABASE_URL` | PostgreSQL connection string | postgresql+asyncpg://... |
| `SECRET_KEY` | JWT signing secret | (change in production!) |
| `JWT_ALGORITHM` | JWT algorithm | HS256 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | 15 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | 7 |
| `CORS_ORIGINS` | Allowed CORS origins | ["http://localhost:8000"] |
| `UPLOAD_DIR` | File upload directory | ../storage/uploads |
| `MAX_UPLOAD_SIZE` | Max upload size (bytes) | 104857600 (100MB) |
| `LOG_LEVEL` | Logging level | INFO |

---

## 📝 Development Log

See [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md) for phase-by-phase progress.

## 📖 Project Explanation

See [docs/PROJECT_EXPLANATION.md](docs/PROJECT_EXPLANATION.md) for comprehensive project documentation.

---

## 📜 License

This project is licensed under the MIT License.

---

## 🏗️ Development Status

| Phase | Name | Status |
|---|---|---|
| Phase 0 | Planning & System Design | ✅ Complete |
| Phase 1 | Project Setup | ✅ Complete |
| Phase 2 | Authentication | ✅ Complete |
| Phase 3 | Dashboard UI | ✅ Complete |
| Phase 4 | Dataset Upload | ✅ Complete |
| Phase 5 | Dataset Profiling | ✅ Complete |
| Phase 6 | Data Quality Engine | ⬜ Not Started |
| Phase 7 | Smart Preprocessing | ⬜ Not Started |
| Phase 8 | EDA Engine | ⬜ Not Started |
| Phase 9 | Feature Engineering | ⬜ Not Started |
| Phase 10 | AutoML Engine | ⬜ Not Started |
| Phase 11 | Model Evaluation | ⬜ Not Started |
| Phase 12 | Explainable AI | ⬜ Not Started |
| Phase 13 | Forecasting Engine | ⬜ Not Started |
| Phase 14 | Anomaly Detection | ⬜ Not Started |
| Phase 15 | AI Business Assistant | ⬜ Not Started |
| Phase 16 | Report Generator | ⬜ Not Started |
| Phase 17 | Deployment | ⬜ Not Started |
| Phase 18 | Enterprise Features | ⬜ Not Started |
