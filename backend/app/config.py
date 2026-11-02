"""Application configuration using Pydantic Settings.

Loads configuration from environment variables and .env file.
All settings are centralized here for easy management.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings

DEFAULT_SECRET_KEY = "your-secret-key-change-in-production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        APP_NAME: Display name of the application.
        APP_VERSION: Current semantic version string.
        DEBUG: Enable debug mode (never True in production).
        DATABASE_URL: Async SQLAlchemy URL. SQLite by default (zero setup);
            use ``postgresql+asyncpg://...`` in production.
        SECRET_KEY: Secret key for JWT signing.
        JWT_ALGORITHM: Algorithm used for JWT encoding.
        ACCESS_TOKEN_EXPIRE_MINUTES: Lifetime of access tokens in minutes.
        REFRESH_TOKEN_EXPIRE_DAYS: Lifetime of refresh tokens in days.
        CORS_ORIGINS: List of allowed CORS origins.
        UPLOAD_DIR: Directory for uploaded datasets.
        MODELS_DIR: Directory for trained model artifacts (.joblib).
        MAX_UPLOAD_SIZE: Maximum upload file size in bytes (default 100MB).
        AUTOML_MAX_ROWS: Rows above this are down-sampled before training.
        ML_N_JOBS: Parallel jobs for cross-validation/tuning (-1 = all cores).
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """

    APP_NAME: str = "AI BI Platform"
    APP_VERSION: str = "0.2.0"
    DEBUG: bool = False

    DATABASE_URL: str = "sqlite+aiosqlite:///./ai_bi_platform.db"

    SECRET_KEY: str = DEFAULT_SECRET_KEY
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    CORS_ORIGINS: list[str] = [
        "http://localhost:8000",
        "http://localhost:3000",
    ]

    UPLOAD_DIR: str = "../storage/uploads"
    MODELS_DIR: str = "../storage/models"
    MAX_UPLOAD_SIZE: int = 104857600  # 100MB

    AUTOML_MAX_ROWS: int = 50000
    ML_N_JOBS: int = 1

    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton.

    Uses lru_cache to avoid re-reading the .env file on every call.

    Returns:
        Settings: The application settings instance.
    """
    return Settings()
