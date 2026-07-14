"""Pydantic schemas for dataset quality results."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class QualityResultRead(BaseModel):
    """Quality analysis result details."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    quality_score: float
    missing_value_report: dict
    duplicate_report: dict
    outlier_report: dict
    correlation_report: dict
    skewness_report: dict
    imbalance_report: dict | None = None
    recommendations: list
    created_at: datetime

    model_config = {"from_attributes": True}
