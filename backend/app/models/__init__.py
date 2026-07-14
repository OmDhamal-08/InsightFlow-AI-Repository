"""ORM model registry.

Import all models here so that ``Base.metadata`` is fully populated
when Alembic or ``init_db()`` inspects it.
"""

from app.models.user import Profile, RefreshToken, User  # noqa: F401
from app.models.dataset import Dataset  # noqa: F401
from app.models.profiling import ProfilingResult  # noqa: F401
from app.models.quality import QualityResult  # noqa: F401
from app.models.pipeline import PreprocessingPipeline  # noqa: F401
from app.models.eda import EdaResult  # noqa: F401
from app.models.feature import FeatureSet  # noqa: F401

__all__ = ["User", "Profile", "RefreshToken", "Dataset", "ProfilingResult", "QualityResult", "PreprocessingPipeline", "EdaResult", "FeatureSet"]
