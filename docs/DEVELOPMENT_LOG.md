# AI-Powered Business Intelligence Platform — Development Log

> **Project Start Date:** 2026-07-12
> **Current Phase:** Phases 0–11 implemented (scope frozen at Phase 11)

---

## Log Format

Each phase entry follows this structure:
- **Phase Number & Name**
- **Start Date / End Date**
- **Objectives** (what was planned)
- **Work Done** (what was actually built)
- **Decisions & Assumptions** (design choices made)
- **Issues Encountered** (problems and how they were resolved)
- **Files Created/Modified** (change manifest)
- **Testing Summary** (what was tested and results)
- **Status** (In Progress / Completed / Approved)

---

## Phase 0 — Planning & System Design

| Field | Value |
|---|---|
| **Start Date** | 2026-07-12 |
| **End Date** | 2026-07-12 |
| **Status** | ✅ Completed — Awaiting Approval |

### Objectives
1. Define the problem statement and target audience
2. Write Software Requirements Specification (SRS)
3. Design high-level system architecture (Mermaid diagrams)
4. Design database schema (ER diagram + table definitions)
5. Design API endpoints (full endpoint list)
6. Define project folder structure (backend + frontend)
7. Create low-fidelity wireframes for 6 pages
8. Map phases to deliverables in a development plan

### Work Done
- [x] Problem Statement — defined business problem, target users, and solution approach
- [x] SRS — functional requirements (19 modules), non-functional requirements (performance, security, scalability), constraints, and assumptions
- [x] Architecture Diagram — layered architecture with client, API gateway, backend services, ML engines, database, and file storage
- [x] Database Design — 15+ tables covering users, datasets, profiling, quality, preprocessing, EDA, features, models, evaluations, SHAP, forecasts, anomalies, conversations, reports, notifications
- [x] API Design — 60+ endpoints across 14 route groups with methods, paths, and descriptions
- [x] Folder Structure — Clean separation: routers/services/repositories/schemas/models (backend), pages/components/utils (frontend)
- [x] Wireframes — ASCII/markdown layouts for Home, Login, Register, Dashboard, Upload, Settings
- [x] Development Plan — All 19 phases mapped to deliverables with estimated complexity

### Decisions & Assumptions
1. **Database:** PostgreSQL chosen for JSON column support (profiling metadata), ACID compliance, and production readiness
2. **Auth Strategy:** JWT with separate access/refresh tokens — access token (15 min), refresh token (7 days), stored in httpOnly cookie (refresh) and memory/localStorage (access)
3. **File Storage:** Local filesystem for Phase 1–16, with abstraction layer to swap to S3 in Phase 17
4. **ML Pipeline Storage:** JSON-serialized pipeline configs in DB + pickled model files on disk
5. **API Versioning:** All endpoints under `/api/v1/` from the start
6. **Frontend Approach:** Server-side rendered HTML pages (not SPA) with JavaScript for interactivity — simpler than React/Vue, demonstrates full-stack capability

### Issues Encountered
- None (planning phase only)

### Files Created
| File | Purpose |
|---|---|
| `docs/PHASE_0_PLANNING.md` | Complete Phase 0 deliverables (SRS, architecture, DB design, API design, folder structure, wireframes, development plan) |
| `docs/PROJECT_EXPLANATION.md` | Comprehensive project explanation document |
| `docs/DEVELOPMENT_LOG.md` | This file — phase-by-phase development log |

### Testing Summary
- N/A (no code in this phase)

---

## Review & Fixes — Full-Project Audit (Phases 0–9 code)

> **Date:** 2026-11-02 · **Status:** ✅ Completed — fixes applied, awaiting sign-off

### Issues Found and Fixed
| Area | Problem | Fix |
|---|---|---|
| Auth tokens | Every token was stamped `type: "access"` (`create_access_token` overwrote the claim), so refresh tokens worked as bearer tokens and reset tokens never verified | Per-type claims (`access` / `refresh` / `reset`); each verifier accepts only its own type |
| Password reset | Reset tokens were rejected as invalid, so reset never worked | Fixed by the token-type change above |
| Refresh / logout | Cookie dependency was an untyped lambda, so FastAPI required a `request` query parameter (422) | Typed `_get_refresh_cookie(request: Request)` |
| Refresh | Naive vs aware datetime comparison (SQLite in tests) | Normalise `expires_at` to UTC |
| Forgot password | Reset token returned to any caller; unknown emails returned 400 (account enumeration) | Token only returned when `DEBUG` is on; identical generic response otherwise |
| Dataset preview | `rows` parameter unbounded | `Query(ge=1, le=500)` |
| Frontend XSS | Dataset names, CSV headers and cell values, server messages, and notifications inserted via `innerHTML` unescaped | `escapeHtml()` helper in `utils.js`; applied across upload, dashboard, main, profiling, quality, preprocessing, features, EDA |
| Dashboard | Recent datasets read `ds.filename` / `ds.size_bytes` (fields don't exist) | Use `ds.name` / `ds.file_size` |
| Docker | Image layout didn't match `main.py` path resolution (frontend, storage and logs would be missing) | Mirror repo layout under `/app/backend`, `/app/frontend`, `/app/storage` |
| Dependencies | `EmailStr` needs `email-validator` (missing); `passlib` unused; `bcrypt` only came in transitively | Added `email-validator` and `bcrypt`; removed `passlib` |
| Build | No `.dockerignore`, so the build context included `venv/`, `.git` and databases | Added `.dockerignore` |

### Files Created/Modified
| File | Change |
|---|---|
| `backend/app/core/security.py` | Token types; `verify_refresh_token` |
| `backend/app/services/auth_service.py` | Refresh uses refresh verifier; reset returns `None` for unknown emails; datetime fix |
| `backend/app/routers/auth.py` | Cookie dependency; forgot-password response |
| `backend/app/routers/datasets.py` | `rows` bounds |
| `backend/tests/test_auth.py` | +8 regression tests (token types, refresh/logout, reset flow, no leakage) |
| `backend/requirements.txt` | `bcrypt`, `email-validator`; `passlib` removed |
| `docker/Dockerfile.backend` | Path layout |
| `.dockerignore` | New |
| `frontend/static/js/*.js` (6 files), `frontend/templates/pages/forgot_password.html` | Escaping, field names, forgot-password UI |
| `README.md` | Status table, structure, `DEBUG` default |

### Known Limitations (not changed)
- No email delivery yet, so in production a password reset cannot be completed. Needs an email sender before Phase 17.
- In `DEBUG` mode the forgot-password response differs for registered and unknown emails (dev-only trade-off).
- `SECRET_KEY` still defaults to a placeholder; should refuse to start with the default when `DEBUG` is off.
- Refresh cookie `secure=False` (should be `True` behind HTTPS).
- Upload reads the whole file into memory before the size check.
- CSV row count counts newline characters, so multi-line quoted fields are miscounted.

### Testing Summary
- Backend: 47 tests pass (39 existing + 8 new auth regression tests).
- Probe of the auth flow before and after the fixes: refresh-as-bearer 200→401, `/refresh` 422→200, reset 400→200, forgot-password token leak removed.
- All frontend scripts pass `node --check`; `escapeHtml` unit cases pass.
- Docker image layout simulated locally: templates, static, uploads and logs resolve correctly.

---

## Phases 10–11 — AutoML Engine & Model Evaluation

> **Date:** 2026-11-02 · **Status:** ✅ Completed

### Scope decision
The project is scoped to **Phases 0–11** and kept lightweight: scikit-learn only (XGBoost/LightGBM optional), no PyTorch, LLM or report libraries. Runtime install measured at **~356 MB**, versus several GB with the old dependency list.

### Work Done
| Area | Change |
|---|---|
| `ml/automl.py` | Task detection, algorithm registry (11 built-in), recommendations by data size, column screening (IDs, constants, free text), sklearn Pipelines, stratified CV, RandomizedSearchCV, failure isolation, `.joblib` bundles, prediction helper |
| `ml/evaluator.py` | Classification and regression metrics, confusion matrix, per-class report, ROC and PR curves, residuals, permutation importance (all JSON-safe) |
| Models + migration | `experiments`, `trained_models` tables (`a3c9e1f4b7d2`), cascade from datasets |
| API | `/api/v1/experiments`: recommend, train, list, detail, model evaluation, predict, download, delete |
| UI | `/experiments` (configure + history), `/experiments/{id}` (leaderboard, Plotly charts, live prediction, download); sidebar, dashboard and dataset links |
| Dashboard | Real trained-model count and average quality score |

### Other improvements
- SQLite is the default database (zero setup); PostgreSQL via Docker.
- Foreign keys are enforced on SQLite, so `ON DELETE CASCADE` actually works.
- Deleting a dataset removes its experiments' model files.
- `alembic.ini` got `prepend_sys_path = .`, so plain `alembic upgrade head` works.
- Docker runs migrations on start; Python 3.12 base image.
- `requirements.txt` split into runtime and dev, with heavy unused libraries removed.
- CI runs migrations, `alembic check` and tests.
- A warning is logged at startup when `SECRET_KEY` is the placeholder.
- Fixed a regression from the previous review: the dashboard "Recent datasets" field names now match the API.
- Replaced deprecated `SVC(probability=True)` with `CalibratedClassifierCV`; SVR scales its target.

### Testing Summary
- **75 tests pass** (47 existing + 28 new: engine unit tests and experiments API).
- Full migration chain applied to a fresh SQLite DB; `alembic check` reports no drift; downgrade and upgrade both verified.
- Browser end-to-end run (Chromium): register → upload → detect task → train 6 tuned models (16 s) → charts → switch model → predict → download → dashboard count, with **0 JavaScript errors**.
- Downloaded `.joblib` loaded and used standalone outside the app.

---

## Full Audit — Every Phase, Every Page

> **Date:** 2026-11-02 · **Status:** ✅ Completed

### Method
1. A messy CSV (missing values, duplicates, outliers, dates, free text, inconsistent casing, column names with spaces/symbols, imbalanced target) was pushed through **every API endpoint**: every preprocessing action, feature method, EDA chart type, and AutoML on raw, cleaned and engineered data.
2. A Playwright walkthrough clicked through **every page**: register, upload via file picker, profiling, quality tabs, recommendation pre-fill, preview and apply, all EDA charts, every feature method, AutoML, dashboard, settings, logout and login, forgot/reset password, stale-session and guest access. It failed on any JS error, unexpected HTTP error or server traceback.

### Bugs found and fixed
| Phase | Bug | Fix |
|---|---|---|
| 2 | Reset-password page could never submit: `checkPasswordStrength()` returned nothing, so every password was "not strong enough" | Returns a level using the server's exact rules |
| 2/3 | A stale or revoked token bounced `/login` to a dashboard that couldn't load (user stuck) | Session confirmed with `/auth/me` before trusting it |
| 2 | Settings page was a fake "demo mode" (profile and password not saved) | Real profile load/save; new `POST /auth/change-password` (revokes other sessions) |
| 4 | Deleting a dataset with EDA charts, feature sets or pipelines failed with an IntegrityError (500) | ORM cascades on all child relationships |
| 6 | Quality engine recommended actions the preprocessor didn't have (`cap_outliers`, `drop_outlier_rows`, `apply_smote`) | Recommendations use real action names |
| 7 | Label encoding, k-means binning and random imputation crashed on pandas 3 (in-place dtype change) | Build complete new columns |
| 7 | "KNN" and "MICE" imputation ignored other columns (MICE was a median fill) | Real `KNNImputer` / `IterativeImputer` using the other numeric columns |
| 7 | Unknown actions, missing columns and numeric actions on text were silently skipped or crashed | Clear 400 errors naming the step |
| 7 | Recommendation pre-fill had an operator-precedence bug and could set invalid dropdown values | Only pre-select options that exist |
| 7 | `apply()` modified the caller's DataFrame | Works on a copy |
| 9 | Polynomial/PCA apply used only the first column's config | Uses every selected column |
| 9 | Feature-selection apply assumed the target was the last column | Target recorded and used |
| 9 | Missing text counted as the word "nan" | Treated as empty |
| 9/10 | ID columns slipped through when the data had duplicate rows; date strings dropped with a misleading reason | Robust ID detector; dates explained |
| All | Unhandled errors dropped the connection | JSON 500 handler with logged traceback |

### Scope clean-up
- Home page now describes only what exists (it advertised SHAP, forecasting, an AI assistant and reports, plus invented stats such as "99.9% uptime").
- Removed out-of-scope "Reports" and "AI Chat" sidebar items, the disabled "Generate Report" button, and non-functional notification and chart-library preferences.
- Dashboard shows experiments instead of an always-empty reports panel.
- Not deleted (no delete access here): `app/utils/file_utils.py` and `app/utils/validators.py` are unused and can be removed.

### Testing Summary
- **98 tests pass** (75 → 98, with 23 new regression tests).
- API flow: 120 calls, 0 failures, 0 server tracebacks.
- Browser walkthrough: 15 stages, 0 JS errors, 0 unexpected HTTP errors.

---

*Subsequent phase entries will be appended below as development progresses.*
