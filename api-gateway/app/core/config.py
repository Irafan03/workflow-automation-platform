"""
api-gateway/app/core/config.py
Paramètres de l'application chargés depuis les variables d'environnement.
"""
from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────
    APP_NAME: str = "workflow-api-gateway"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")
    API_SECRET_KEY: str = Field(default="changeme")

    # ── PostgreSQL ────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://workflow_user:changeme@localhost:5432/workflow_db"
    )
    DB_ECHO: bool = Field(default=False)   # True = log SQL (debug only)

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://:changeme@localhost:6379/0")

    # ── MLflow ────────────────────────────────────────────────
    MLFLOW_TRACKING_URI: str = Field(default="http://mlflow:5000")

    # ── CORS ──────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def ensure_async_driver(cls, v: str) -> str:
        """Force le driver asyncpg pour SQLAlchemy async."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
