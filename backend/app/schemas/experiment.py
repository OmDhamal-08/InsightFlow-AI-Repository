"""Pydantic schemas for AutoML experiments and model evaluation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ExperimentCreate(BaseModel):
    """Request to train and compare models on a dataset."""

    dataset_id: uuid.UUID
    target_column: str = Field(..., min_length=1, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    algorithms: list[str] | None = Field(
        default=None, max_length=12, description="Algorithm keys; omit to use the recommended set"
    )
    optimize_metric: str | None = Field(default=None, description="Metric used to rank models")
    test_size: float = Field(default=0.2, ge=0.1, le=0.4)
    cv_folds: int = Field(default=5, ge=2, le=10)
    tune_hyperparameters: bool = False
    tuning_iterations: int = Field(default=10, ge=2, le=30)


class AlgorithmOption(BaseModel):
    key: str
    name: str
    description: str
    recommended: bool
    reason: str
    tunable: bool


class MetricOption(BaseModel):
    key: str
    label: str


class RecommendationResponse(BaseModel):
    """Detected task type plus suggested algorithms for a dataset/target pair."""

    dataset_id: uuid.UUID
    target_column: str
    task_type: str
    n_rows: int
    target_unique_values: int
    target_preview: dict[str, int] | None = None
    algorithms: list[AlgorithmOption]
    metrics: list[MetricOption]
    default_metric: str


class TrainedModelSummary(BaseModel):
    """One leaderboard row (no heavy chart data)."""

    id: uuid.UUID
    algorithm: str
    display_name: str
    status: str
    rank: int | None = None
    is_best: bool
    cv_score: float | None = None
    cv_std: float | None = None
    test_score: float | None = None
    metrics: dict
    hyperparameters: dict
    training_time_seconds: float | None = None
    error_message: str | None = None

    model_config = {"from_attributes": True}


class TrainedModelDetail(TrainedModelSummary):
    """A trained model including its evaluation charts data."""

    experiment_id: uuid.UUID
    evaluation: dict
    has_artifact: bool = False


class ExperimentSummary(BaseModel):
    """Experiment row for list views."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    dataset_name: str | None = None
    name: str
    target_column: str
    task_type: str | None = None
    optimize_metric: str | None = None
    status: str
    best_model_id: uuid.UUID | None = None
    best_model_name: str | None = None
    best_score: float | None = None
    model_count: int = 0
    training_time_seconds: float | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ExperimentDetail(ExperimentSummary):
    """Experiment with its configuration, data summary and leaderboard."""

    config: dict
    summary: dict | None = None
    metric_label: str | None = None
    lower_is_better: bool = False
    models: list[TrainedModelSummary]


class PredictRequest(BaseModel):
    """Raw input rows keyed by original column name."""

    rows: list[dict] = Field(..., min_length=1, max_length=1000)


class PredictResponse(BaseModel):
    model_id: uuid.UUID
    task_type: str
    predictions: list[dict]
