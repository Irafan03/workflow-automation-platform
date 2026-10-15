"""
trigger-service/app/adapters/telegram.py
Adaptateur pour les mises à jour Telegram Bot API (mode webhook).

Sécurité :
  Telegram envoie un header X-Telegram-Bot-Api-Secret-Token
  que l'on compare au TELEGRAM_WEBHOOK_SECRET configuré.
  Ref: https://core.telegram.org/bots/api#setwebhook
"""
import hmac
from typing import Any

import structlog
from fastapi import HTTPException, Request, status
from pydantic import ValidationError

from app.adapters.base import BaseAdapter
from app.core.config import settings
from app.normalizer import normalize
from app.schemas.events import EventSource, NormalizedEvent, TelegramUpdate

logger = structlog.get_logger(__name__)


class TelegramAdapter(BaseAdapter):
    """
    Reçoit les updates Telegram envoyés par le Bot API en mode webhook.

    Flux :
    1. Telegram POST → /api/v1/triggers/telegram
    2. Vérification du secret token dans le header
    3. Validation du payload comme TelegramUpdate
    4. Normalisation → NormalizedEvent
    5. Publication dans Redis
    """

    source_name = "telegram"

    async def verify_signature(self, request: Request) -> bool:
        """
        Vérifie le header X-Telegram-Bot-Api-Secret-Token.
        Absent → rejeté (Telegram doit toujours l'envoyer si configuré).
        """
        if not settings.TELEGRAM_WEBHOOK_SECRET:
            # Secret non configuré : on passe (dev only)
            logger.warning("TELEGRAM_WEBHOOK_SECRET not set, skipping verification")
            return True

        token = request.headers.get("x-telegram-bot-api-secret-token", "")
        return hmac.compare_digest(token, settings.TELEGRAM_WEBHOOK_SECRET)

    async def validate(self, request: Request) -> TelegramUpdate:
        """Parse le corps JSON comme un TelegramUpdate."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Corps JSON invalide reçu de Telegram.",
            )

        try:
            return TelegramUpdate(**body)
        except ValidationError as exc:
            logger.warning(
                "telegram update validation failed",
                errors=exc.errors(),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )

    async def normalize(
        self, raw: TelegramUpdate, meta: dict[str, Any] | None = None
    ) -> NormalizedEvent:
        # Enrichit les méta avec l'update_id pour la déduplication
        enriched_meta = {**(meta or {}), "telegram_update_id": raw.update_id}
        return normalize(EventSource.TELEGRAM, raw, enriched_meta)


# ── Simulation : générateur d'update Telegram factice ────────────────────────

def build_fake_telegram_update(
    chat_id: int = 123456789,
    text: str = "Hello from simulation!",
    update_id: int = 1,
) -> dict[str, Any]:
    """
    Génère un payload TelegramUpdate simulé pour les tests / démos.
    Utilisé par la route POST /api/v1/triggers/telegram/simulate.
    """
    import time
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "from": {
                "id": 987654321,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser",
            },
            "chat": {
                "id": chat_id,
                "type": "private",
                "first_name": "Test",
                "username": "testuser",
            },
            "date": int(time.time()),
            "text": text,
        },
    }


# Singleton réutilisable par les routes FastAPI
telegram_adapter = TelegramAdapter()
