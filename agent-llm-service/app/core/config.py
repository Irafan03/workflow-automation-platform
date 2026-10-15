"""
agent-llm-service/app/core/config.py
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
    APP_NAME: str = "workflow-agent-llm-service"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # ── LLM Backend ───────────────────────────────────────────
    # Provider actif : "ollama" | "openai"
    LLM_PROVIDER: str = Field(default="ollama")

    # Ollama (modèle local conteneurisé)
    OLLAMA_BASE_URL: str = Field(default="http://ollama:11434")
    OLLAMA_MODEL: str = Field(default="gemma:2b")

    # OpenAI (fallback cloud)
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")

    # Paramètres LLM par défaut (surchargeables par requête)
    LLM_DEFAULT_TEMPERATURE: float = Field(default=0.7, ge=0.0, le=2.0)
    LLM_DEFAULT_MAX_TOKENS: int = Field(default=1024, ge=1, le=8192)
    LLM_REQUEST_TIMEOUT: int = Field(default=120)  # secondes

    # ── MLflow ────────────────────────────────────────────────
    MLFLOW_TRACKING_URI: str = Field(default="http://mlflow:5000")
    MLFLOW_EXPERIMENT_NAME: str = Field(default="agent-llm-inference")

    # ── CORS ──────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )


settings = Settings()
