"""
trigger-service/app/adapters/webhook.py
Adaptateur pour les webhooks HTTP entrants génériques.
Validation optionnelle via HMAC-SHA256 (header X-Webhook-Signature).
"""
import hashlib
import hmac
from typing import Any

import structlog
from fastapi import HTTPException, Request, status
from pydantic import ValidationError

from app.adapters.base import BaseAdapter
from app.core.config import settings
from app.normalizer import normalize
from app.schemas.events import EventSource, NormalizedEvent, WebhookPayload

logger = structlog.get_logger(__name__)


class WebhookAdapter(BaseAdapter):
    """
    Traite les webhooks HTTP génériques (JSON).

    Signature optionnelle :
      Header: X-Webhook-Signature: sha256=<hex_digest>
      Calculé sur le corps brut avec WEBHOOK_SECRET comme clé HMAC.

    Si le header est absent → accepté sans vérification (mode permissif).
    Si présent → vérification stricte.
    """

    source_name = "webhook"

    async def verify_signature(self, request: Request) -> bool:
        """Vérifie le HMAC-SHA256 si le header X-Webhook-Signature est présent."""
        signature_header = request.headers.get("x-webhook-signature")
        if not signature_header:
            # Pas de signature fournie — accepté en mode permissif
            return True

        if not signature_header.startswith("sha256="):
            logger.warning("webhook signature missing sha256 prefix")
            return False

        body = await request.body()
        expected_sig = hmac.new(
            settings.WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        received_sig = signature_header.removeprefix("sha256=")

        # Comparaison à temps constant pour éviter les timing attacks
        return hmac.compare_digest(expected_sig, received_sig)

    async def validate(self, request: Request) -> WebhookPayload:
        """Parse et valide le JSON entrant comme WebhookPayload."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Corps de la requête JSON invalide ou malformé.",
            )

        try:
            return WebhookPayload(**body)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )

    async def normalize(
        self, raw: WebhookPayload, meta: dict[str, Any] | None = None
    ) -> NormalizedEvent:
        return normalize(EventSource.WEBHOOK, raw, meta)


# Singleton réutilisable par les routes FastAPI
webhook_adapter = WebhookAdapter()
