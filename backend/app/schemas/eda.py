"""Pydantic schemas for Exploratory Data Analysis (EDA) results."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class EdaCustomRequest(BaseModel):
    """Request payload to calculate a custom exploratory plot dynamically."""

    chart_type: str = Field(..., description="distribution, boxplot, qq_plot, scatter")
    columns: list[str] = Field(..., min_length=1, max_length=2, description="Target column(s) to analyze")


class EdaResultRead(BaseModel):
    """Details of a calculated EDA chart."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    chart_type: str
    chart_config: dict
    chart_data: dict
    insight: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
