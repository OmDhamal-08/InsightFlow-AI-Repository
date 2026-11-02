"""Shared helper for loading a stored dataset file into a DataFrame."""

import logging
from pathlib import Path

import pandas as pd

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.dataset import Dataset

logger = logging.getLogger(__name__)


def load_dataset_frame(dataset: Dataset) -> pd.DataFrame:
    """Read a dataset's CSV/Excel file from disk.

    Raises:
        NotFoundException: The file is missing from storage.
        BadRequestException: The file type is unsupported or cannot be parsed.
    """
    file_path = Path(dataset.file_path)
    if not file_path.exists():
        raise NotFoundException(detail="Dataset file missing from storage")
    try:
        if dataset.file_type == "csv":
            return pd.read_csv(file_path)
        if dataset.file_type in ("xlsx", "xls"):
            return pd.read_excel(file_path)
    except Exception as exc:
        logger.error("Failed to load dataset file %s: %s", file_path, exc)
        raise BadRequestException(detail=f"Could not load dataset file: {exc}") from exc
    raise BadRequestException(detail=f"Unsupported file type: {dataset.file_type}")
