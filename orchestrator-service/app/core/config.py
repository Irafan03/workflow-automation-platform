"""
orchestrator-service/app/core/config.py
Paramètres de configuration chargés depuis les variables d'environnement.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────
    APP_NAME: str = "workflow-orchestrator-service"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # ── Health HTTP ───────────────────────────────────────────
    HEALTH_PORT: int = Field(default=8003)

    # ── PostgreSQL ────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://workflow_user:changeme@localhost:5432/workflow_db"
    )
    DB_ECHO: bool = Field(default=False)
    DB_POOL_SIZE: int = Field(default=5)
    DB_MAX_OVERFLOW: int = Field(default=10)

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://:changeme@localhost:6379/0")
    # File d'attente sur laquelle écoute l'orchestrateur (doit correspondre
    # au REDIS_EVENTS_QUEUE du trigger-service)
    REDIS_EVENTS_QUEUE: str = Field(default="workflow:events")
    # Timeout BLPOP en secondes (0 = infini)
    REDIS_BLPOP_TIMEOUT: int = Field(default=5)

    # ── Agent LLM Service ─────────────────────────────────────
    AGENT_LLM_URL: str = Field(default="http://agent-llm-service:8002")
    AGENT_LLM_TIMEOUT: int = Field(default=120)  # secondes

    # ── Concurrence ───────────────────────────────────────────
    # Nombre max de workflows pouvant s'exécuter en parallèle
    ORCHESTRATOR_CONCURRENCY: int = Field(default=4)

    @property
    def database_url_sync(self) -> str:
        """Version synchrone de l'URL (pour d'éventuels outils CLI)."""
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

    def ensure_async_driver(self) -> None:
        """Force le driver asyncpg si l'URL utilise le schéma simple."""
        if self.DATABASE_URL.startswith("postgresql://"):
            object.__setattr__(
                self,
                "DATABASE_URL",
                self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1),
            )


settings = Settings()
settings.ensure_async_driver()
