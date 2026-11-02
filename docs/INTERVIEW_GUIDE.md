# Interview Guide — AutoML BI Platform

How to put this project on your resume and talk about it confidently. Every number here comes from the actual code and tests.

---

## 1. One-line description (resume / LinkedIn)

> Full-stack AutoML platform (FastAPI, scikit-learn, SQLAlchemy) that takes a CSV from upload through profiling, data-quality scoring, preprocessing, EDA and feature engineering to automated model training, evaluation and a prediction API.

## 2. Resume bullets (pick 3–4)

- Built a **full-stack AutoML platform** in **FastAPI + scikit-learn** that automates the ML workflow: upload, profiling, data-quality scoring, preprocessing, EDA, feature engineering, model training and evaluation, across **45 REST endpoints**.
- Designed an **AutoML engine** that auto-detects the task (binary, multiclass, regression), recommends algorithms by data size, and trains **11 algorithms** as leakage-safe sklearn **Pipelines** with **stratified k-fold CV** and **randomized hyperparameter search**.
- Implemented **model evaluation**: leaderboard with best-model selection, confusion matrix, **ROC / precision-recall curves**, residual analysis and **permutation feature importance**, rendered interactively with Plotly.
- Served trained models through an authenticated **prediction API** and **.joblib export**, with per-user isolation, **JWT access/refresh tokens with rotation**, and XSS-safe rendering.
- Kept the stack **lightweight (~350 MB install, no GPU/PyTorch)**, with **98 automated tests** plus a Playwright browser walkthrough, **9 Alembic migrations** validated in **GitHub Actions CI**, and Docker deployment on PostgreSQL.

## 3. The 30-second pitch

> "It's a no-code machine-learning platform. You upload a spreadsheet, and it profiles every column, gives the data a quality score with fixes, lets you clean and explore it, then trains and compares up to eleven models automatically. You get a leaderboard, ROC curves, a confusion matrix and feature importance, and you can call the best model through an API or download it. The backend is FastAPI with a clean layered architecture, and the ML is all scikit-learn, so it installs in about 350 MB."

## 4. The 2-minute walkthrough (live demo order)

1. **Upload** a churn CSV. Mention SHA-256 duplicate detection and file validation.
2. **Profiling and quality.** Show the automatic column types, the 0–100 quality score and its plain-English recommendations.
3. **EDA.** Pick the target and show the statistical tests (ANOVA, chi-square with Cramér's V) ranking features.
4. **Train Models.** Select `churned`. The app detects *binary classification* and pre-selects recommended algorithms. Turn on tuning and train.
5. **Evaluation.** Show the leaderboard. Explain that the winner is chosen on cross-validation and the test score is unbiased. Then show the confusion matrix, ROC curve and feature importance.
6. **Try a prediction**, then **download** the `.joblib` and point out it's a plain sklearn pipeline usable anywhere.

## 5. Architecture talk track

```
Browser (Jinja2 + JS + Plotly) ──REST/JWT──> Routers → Services → Repositories → SQLite/PostgreSQL
                                                         └──> ml/ (pandas, scikit-learn) → storage/ (uploads, models)
```

- **Routers** only handle HTTP and validation (Pydantic).
- **Services** hold business rules: ownership checks, orchestration, persistence.
- **Repositories** hold every SQL query, which keeps services testable.
- **`ml/`** has no web or database imports. It is pure functions over DataFrames, unit-tested on its own.
- Training is CPU-bound, so it runs in `run_in_threadpool` and doesn't block the async event loop.

## 6. Deep dives you should be ready for

**How does task detection work?**
Two distinct values means binary. Text, booleans, or integers with at most 20 distinct values (under 50% unique) mean multiclass. Any other numeric target is regression. The rules are simple on purpose, so they're easy to explain and test.

**How do you avoid data leakage?**
Imputation, scaling and one-hot encoding live *inside* the sklearn `Pipeline`. During cross-validation they are re-fit on each training fold only, so validation folds never influence preprocessing. The same fitted pipeline is saved, so production predictions get identical preprocessing.

**Why rank on CV score instead of the test score?**
If you pick the best of N models by test score, you've tuned to the test set and the reported number is optimistic. CV picks the model; the untouched test split gives the honest final estimate.

**Which metric and why?**
- The default is weighted F1 for classification, which is robust to class imbalance, and R² for regression.
- Users can switch to accuracy, ROC-AUC, RMSE or MAE.
- Error metrics are "lower is better", so the leaderboard sorts them ascending (sklearn returns them negated internally).

**Why permutation importance instead of built-in `feature_importances_`?**
It works for every model, including linear models, KNN and SVM. It's measured on held-out data, and it's reported on the original columns instead of one-hot-expanded ones. Built-in tree importances are also known to be biased toward high-cardinality features.

**Why is SVM wrapped in `CalibratedClassifierCV`?**
SVMs don't output probabilities, and ROC-AUC and the ROC curves need them. Calibration provides proper probabilities, and it's scikit-learn's recommended replacement for the deprecated `SVC(probability=True)`. For regression, SVR also standardises the target, which raised its cross-validated R² from 0.14 to 0.95 on a sample dataset.

**What happens if one algorithm crashes?**
The failure is recorded on that model (status `failed` plus the message) and the others continue. Invalid input (wrong metric for the task, too few rows) is rejected with a 400 *before* anything is stored.

**How is it secured?**
- Access tokens last 15 minutes; refresh tokens are in an httpOnly cookie and are rotated and revocable.
- Each token type is verified separately, so a refresh token can't be used as an access token.
- Every query is scoped by user, and other users' resources return 404.
- User-controlled text (file names, CSV headers and cells) is HTML-escaped before rendering, to prevent stored XSS.

**How is it tested?**
- 98 pytest tests on an in-memory SQLite database with temporary storage, plus a Playwright walkthrough that clicks through every page.
- Engine unit tests cover task detection, column dropping, every task type, tuning, error-metric ranking and failure isolation.
- API tests cover the full train → evaluate → predict → download → delete lifecycle, validation errors, cross-user access and cascading deletes.
- CI runs `alembic upgrade head`, `alembic check` and the test suite.

## 7. Honest limitations (say these before they ask)

- Training runs during the request, which is fine up to the 50k-row cap. For bigger jobs I'd move it to a task queue (Celery or RQ) with progress polling.
- Hyperparameter search is randomized, not Bayesian. Optuna would be the upgrade if accuracy mattered more than simplicity.
- If you train on a dataset already transformed by the preprocessing page, those transformations were fit on all rows. The AutoML pipeline itself is leakage-safe.
- There's no email service, so password reset links only appear in debug mode.
- Files are stored on local disk; S3 would be the production choice.

## 8. Likely questions — short answers

| Question | Answer |
|---|---|
| Why FastAPI? | Async I/O, Pydantic validation, automatic OpenAPI docs, and it's fast to build with. |
| Why not deep learning? | Tabular business data is usually won by tree ensembles; a GPU stack would add GBs for no accuracy gain. |
| How would you scale it? | Task queue for training, PostgreSQL, S3 for files, multiple uvicorn workers behind Nginx. |
| How do you handle imbalanced classes? | Stratified splits and folds, weighted F1 by default, PR curves on the evaluation page, and the quality engine flags imbalance. |
| What's in the `.joblib`? | The fitted pipeline plus metadata: feature columns, numeric/categorical lists, class labels, task type. |
| Hardest bug? | Refresh and reset tokens were all stamped as `access` tokens, so refresh tokens worked as bearer tokens and password reset never verified. I fixed it with per-type token claims and added regression tests. |
| How did you test it end to end? | I pushed a deliberately messy CSV (missing values, duplicates, outliers, dates, free text, odd column names) through all 45 endpoints, then clicked through every page in Playwright. That found real bugs: pandas 3 dtype errors in label encoding, dataset deletion failing on child rows, and a reset-password page that could never submit. |
| How do you stop ID columns leaking into models? | Integer columns that are ~95%+ unique and either consecutive or named like an ID are dropped, with the reason shown. The 5% slack matters because duplicate rows make a real ID column slightly non-unique. |
