"""
trigger-service/app/core/config.py
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
    APP_NAME: str = "workflow-trigger-service"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = Field(default="redis://:changeme@localhost:6379/0")

    # Nom de la file Redis dans laquelle les événements normalisés sont poussés
    REDIS_EVENTS_QUEUE: str = Field(default="workflow:events")

    # TTL (secondes) d'un événement en cas d'utilisation de Redis Streams
    REDIS_EVENT_TTL: int = Field(default=86400)   # 24h

    # ── Sécurité Webhooks ─────────────────────────────────────
    # Secret HMAC-SHA256 pour valider les webhooks entrants
    WEBHOOK_SECRET: str = Field(default="changeme_webhook_secret")

    # ── Telegram ──────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_WEBHOOK_SECRET: str = Field(default="changeme_telegram_secret")

    # ── Gmail OAuth2 (simulé) ─────────────────────────────────
    GMAIL_CLIENT_ID: str = Field(default="")
    GMAIL_CLIENT_SECRET: str = Field(default="")
    GMAIL_WEBHOOK_TOKEN: str = Field(default="changeme_gmail_token")

    # ── CORS ──────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )


settings = Settings()
