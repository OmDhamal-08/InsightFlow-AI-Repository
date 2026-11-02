"""Business logic for AutoML experiments (Phase 10) and model evaluation (Phase 11).

The heavy lifting lives in ``app.ml.automl`` / ``app.ml.evaluator``. This layer:
  * checks ownership and validates the request,
  * runs training in a worker thread so the async event loop stays responsive,
  * persists the experiment, leaderboard and evaluation data,
  * serves predictions and model downloads from the saved ``.joblib`` files.
"""

import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.ml import automl
from app.models.dataset import Dataset
from app.models.experiment import Experiment, TrainedModel
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.experiment_repository import ExperimentRepository
from app.schemas.experiment import ExperimentCreate
from app.utils.dataset_io import load_dataset_frame

logger = logging.getLogger(__name__)


def experiment_artifact_dir(experiment_id: uuid.UUID) -> Path:
    """Folder holding the ``.joblib`` files for one experiment."""
    return Path(get_settings().MODELS_DIR) / str(experiment_id)


def remove_experiment_artifacts(experiment_id: uuid.UUID) -> None:
    shutil.rmtree(experiment_artifact_dir(experiment_id), ignore_errors=True)


class ExperimentService:
    """Create, train, inspect and serve AutoML experiments."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ExperimentRepository(db)
        self.dataset_repo = DatasetRepository(db)

    # ── Recommendations ──────────────────────────────────────────

    async def recommend(self, dataset_id: uuid.UUID, target_column: str, user_id: uuid.UUID) -> dict:
        """Detect the task type for a target and list suitable algorithms and metrics."""
        dataset = await self._get_dataset(dataset_id, user_id)
        df = load_dataset_frame(dataset)
        if target_column not in df.columns:
            raise BadRequestException(detail=f"Column '{target_column}' not found in dataset")

        target = df[target_column]
        try:
            task = automl.detect_task_type(target)
        except automl.AutoMLError as exc:
            raise BadRequestException(detail=str(exc)) from exc

        preview = None
        if task in automl.CLASSIFICATION_TASKS:
            counts = target.dropna().astype(str).value_counts().head(10)
            preview = {str(k): int(v) for k, v in counts.items()}

        metrics = automl.metrics_for_task(task)
        return {
            "dataset_id": dataset_id,
            "target_column": target_column,
            "task_type": task,
            "n_rows": int(target.notna().sum()),
            "target_unique_values": int(target.nunique()),
            "target_preview": preview,
            "algorithms": automl.recommend_algorithms(task, int(target.notna().sum())),
            "metrics": [{"key": k, "label": label} for k, (_s, label) in metrics.items()],
            "default_metric": automl.default_metric(task),
        }

    # ── Training ─────────────────────────────────────────────────

    async def create_experiment(self, user_id: uuid.UUID, req: ExperimentCreate) -> dict:
        """Train and compare models, then persist the leaderboard.

        Input problems the user can fix (bad target, too few rows, wrong
        algorithm for the task) raise 400 and store nothing. Unexpected
        training failures are recorded on the experiment as ``failed``.
        """
        dataset = await self._get_dataset(req.dataset_id, user_id)
        df = load_dataset_frame(dataset)
        if req.target_column not in df.columns:
            raise BadRequestException(detail=f"Column '{req.target_column}' not found in dataset")

        # Validate cheap, user-fixable choices before anything is stored.
        try:
            task = automl.detect_task_type(df[req.target_column])
            automl.validate_choices(task, req.algorithms, req.optimize_metric)
        except automl.AutoMLError as exc:
            raise BadRequestException(detail=str(exc)) from exc

        settings = get_settings()
        config = automl.AutoMLConfig(
            target_column=req.target_column,
            algorithms=req.algorithms or None,
            optimize_metric=req.optimize_metric,
            test_size=req.test_size,
            cv_folds=req.cv_folds,
            tune_hyperparameters=req.tune_hyperparameters,
            tuning_iterations=req.tuning_iterations,
            max_rows=settings.AUTOML_MAX_ROWS,
            n_jobs=settings.ML_N_JOBS,
        )

        experiment = await self.repo.create(
            user_id=user_id,
            dataset=dataset,
            dataset_id=dataset.id,
            name=req.name or f"{Path(dataset.name).stem} → {req.target_column}",
            target_column=req.target_column,
            status="running",
            config={
                "algorithms": req.algorithms,
                "optimize_metric": req.optimize_metric,
                "test_size": req.test_size,
                "cv_folds": req.cv_folds,
                "tune_hyperparameters": req.tune_hyperparameters,
                "tuning_iterations": req.tuning_iterations,
            },
            models=[],
        )
        artifact_dir = experiment_artifact_dir(experiment.id)
        logger.info("Experiment %s: training on dataset %s (target=%s)", experiment.id, dataset.id, req.target_column)

        try:
            result = await run_in_threadpool(automl.run_automl, df, config, artifact_dir)
        except automl.AutoMLError as exc:
            # e.g. too few rows per class — nothing useful to keep
            remove_experiment_artifacts(experiment.id)
            await self.repo.delete(experiment)
            raise BadRequestException(detail=str(exc)) from exc
        except Exception as exc:  # unexpected: keep a record so the user can see what happened
            logger.exception("Experiment %s failed", experiment.id)
            remove_experiment_artifacts(experiment.id)
            experiment.status = "failed"
            experiment.error_message = str(exc)[:1000]
            experiment.completed_at = datetime.now(timezone.utc)
            await self.db.flush()
            return self._to_detail(experiment)

        for entry in result["models"]:
            experiment.models.append(TrainedModel(
                id=entry["id"],
                algorithm=entry["algorithm"],
                display_name=entry["display_name"],
                status=entry["status"],
                hyperparameters=entry["hyperparameters"],
                cv_score=entry["cv_score"],
                cv_std=entry["cv_std"],
                test_score=entry["test_score"],
                metrics=entry["metrics"],
                evaluation=entry["evaluation"],
                artifact_path=entry["artifact_path"],
                training_time_seconds=entry["training_time_seconds"],
                rank=entry["rank"],
                is_best=entry["is_best"],
                error_message=entry["error_message"],
            ))
        experiment.models.sort(key=lambda m: (m.rank is None, m.rank or 0))

        experiment.task_type = result["task_type"]
        experiment.optimize_metric = result["optimize_metric"]
        experiment.summary = {
            **result["summary"],
            "metric_label": result["metric_label"],
            "lower_is_better": result["lower_is_better"],
        }
        experiment.best_model_id = result["best_model_id"]
        experiment.training_time_seconds = result["training_time_seconds"]
        experiment.completed_at = datetime.now(timezone.utc)
        if result["best_model_id"] is None:
            experiment.status = "failed"
            experiment.error_message = "Every algorithm failed to train — see each model's error message."
        else:
            experiment.status = "completed"
        await self.db.flush()
        logger.info("Experiment %s %s in %.1fs", experiment.id, experiment.status, experiment.training_time_seconds)
        return self._to_detail(experiment)

    # ── Queries ──────────────────────────────────────────────────

    async def list_experiments(self, user_id: uuid.UUID, dataset_id: uuid.UUID | None = None) -> list[dict]:
        experiments = await self.repo.list_by_user(user_id, dataset_id)
        return [self._to_summary(e) for e in experiments]

    async def get_experiment(self, experiment_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        return self._to_detail(await self._get_experiment(experiment_id, user_id))

    async def get_model(self, experiment_id: uuid.UUID, model_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        experiment = await self._get_experiment(experiment_id, user_id)
        model = self._find_model(experiment, model_id)
        data = self._model_row(model)
        data.update({
            "experiment_id": experiment.id,
            "evaluation": model.evaluation or {},
            "has_artifact": bool(model.artifact_path and Path(model.artifact_path).exists()),
        })
        return data

    async def get_artifact_path(self, experiment_id: uuid.UUID, model_id: uuid.UUID, user_id: uuid.UUID) -> tuple[Path, str]:
        experiment = await self._get_experiment(experiment_id, user_id)
        model = self._find_model(experiment, model_id)
        path = Path(model.artifact_path) if model.artifact_path else None
        if not path or not path.exists():
            raise NotFoundException(detail="Model file not found")
        safe_target = "".join(c if c.isalnum() else "_" for c in experiment.target_column)
        return path, f"{model.algorithm}_{safe_target}.joblib"

    async def predict(self, experiment_id: uuid.UUID, model_id: uuid.UUID, user_id: uuid.UUID, rows: list[dict]) -> dict:
        path, _ = await self.get_artifact_path(experiment_id, model_id, user_id)
        bundle = await run_in_threadpool(automl.load_model_bundle, path)
        try:
            predictions = await run_in_threadpool(automl.predict_with_bundle, bundle, rows)
        except Exception as exc:
            raise BadRequestException(detail=f"Prediction failed: {exc}") from exc
        return {"model_id": model_id, "task_type": bundle["task_type"], "predictions": predictions}

    async def delete_experiment(self, experiment_id: uuid.UUID, user_id: uuid.UUID) -> None:
        experiment = await self._get_experiment(experiment_id, user_id)
        await self.repo.delete(experiment)
        remove_experiment_artifacts(experiment_id)

    async def count_trained_models(self, user_id: uuid.UUID) -> int:
        return await self.repo.count_trained_models(user_id)

    # ── Helpers ──────────────────────────────────────────────────

    async def _get_dataset(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> Dataset:
        dataset = await self.dataset_repo.get_by_id(dataset_id, user_id)
        if not dataset:
            raise NotFoundException(detail="Dataset not found")
        return dataset

    async def _get_experiment(self, experiment_id: uuid.UUID, user_id: uuid.UUID) -> Experiment:
        experiment = await self.repo.get_by_id(experiment_id, user_id)
        if not experiment:
            raise NotFoundException(detail="Experiment not found")
        return experiment

    @staticmethod
    def _find_model(experiment: Experiment, model_id: uuid.UUID) -> TrainedModel:
        for model in experiment.models:
            if model.id == model_id:
                return model
        raise NotFoundException(detail="Model not found in this experiment")

    @staticmethod
    def _model_row(model: TrainedModel) -> dict:
        return {
            "id": model.id,
            "algorithm": model.algorithm,
            "display_name": model.display_name,
            "status": model.status,
            "rank": model.rank,
            "is_best": model.is_best,
            "cv_score": model.cv_score,
            "cv_std": model.cv_std,
            "test_score": model.test_score,
            "metrics": model.metrics or {},
            "hyperparameters": model.hyperparameters or {},
            "training_time_seconds": model.training_time_seconds,
            "error_message": model.error_message,
        }

    def _to_summary(self, experiment: Experiment) -> dict:
        best = next((m for m in experiment.models if m.is_best), None)
        return {
            "id": experiment.id,
            "dataset_id": experiment.dataset_id,
            "dataset_name": experiment.dataset.name if experiment.dataset else None,
            "name": experiment.name,
            "target_column": experiment.target_column,
            "task_type": experiment.task_type,
            "optimize_metric": experiment.optimize_metric,
            "status": experiment.status,
            "best_model_id": experiment.best_model_id,
            "best_model_name": best.display_name if best else None,
            "best_score": best.test_score if best else None,
            "model_count": sum(1 for m in experiment.models if m.status == "completed"),
            "training_time_seconds": experiment.training_time_seconds,
            "error_message": experiment.error_message,
            "created_at": experiment.created_at,
            "completed_at": experiment.completed_at,
        }

    def _to_detail(self, experiment: Experiment) -> dict:
        summary = experiment.summary or {}
        data = self._to_summary(experiment)
        data.update({
            "config": experiment.config or {},
            "summary": summary or None,
            "metric_label": summary.get("metric_label"),
            "lower_is_better": bool(summary.get("lower_is_better", False)),
            "models": [self._model_row(m) for m in experiment.models],
        })
        return data
