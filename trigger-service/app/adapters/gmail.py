"""
trigger-service/app/adapters/gmail.py
Adaptateur Gmail — notifications push via Google Cloud Pub/Sub (simulé).

Architecture réelle :
  Gmail → Pub/Sub topic → Pub/Sub push subscription → POST /api/v1/triggers/gmail

Simulation :
  Un token de vérification statique (GMAIL_WEBHOOK_TOKEN) est comparé au
  query-param `token` envoyé par Pub/Sub lors de la validation de l'URL.
  Les messages Pub/Sub incluent une charge utile JSON base64.

Ref: https://developers.google.com/gmail/api/guides/push
"""
import base64
import json
from typing import Any

import structlog
from fastapi import HTTPException, Request, status
from pydantic import ValidationError

from app.adapters.base import BaseAdapter
from app.core.config import settings
from app.normalizer import normalize
from app.schemas.events import EventSource, GmailPubSubMessage, NormalizedEvent

logger = structlog.get_logger(__name__)

# Structure attendue d'un push Pub/Sub de Google
# {
#   "message": {
#     "data": "<base64 JSON>",
#     "messageId": "...",
#     "publishTime": "..."
#   },
#   "subscription": "projects/.../subscriptions/..."
# }


class GmailAdapter(BaseAdapter):
    """
    Reçoit et traite les notifications push Gmail via Google Pub/Sub.

    Vérification :
      - Query param `token` comparé à GMAIL_WEBHOOK_TOKEN (validation URL Pub/Sub)
      - En production : vérifier le JWT Google OIDC dans Authorization header

    Simulation :
      La route /api/v1/triggers/gmail/simulate permet de pousser un événement
      Gmail factice sans avoir à configurer OAuth2.
    """

    source_name = "gmail"

    async def verify_signature(self, request: Request) -> bool:
        """
        Vérifie le token de validation Pub/Sub dans les query params.
        Google envoie ?token=<GMAIL_WEBHOOK_TOKEN> lors de la validation initiale
        et sur chaque push si configuré.
        """
        if not settings.GMAIL_WEBHOOK_TOKEN:
            logger.warning("GMAIL_WEBHOOK_TOKEN not set, skipping verification")
            return True

        token = request.query_params.get("token", "")
        if not token:
            # Certains setups n'envoient pas le token sur chaque message
            # En production, valider le JWT OIDC à la place
            logger.warning("gmail push received without token query param")
            return True   # permissif pour la démo

        import hmac
        return hmac.compare_digest(token, settings.GMAIL_WEBHOOK_TOKEN)

    async def validate(self, request: Request) -> GmailPubSubMessage:
        """
        Parse le body JSON Pub/Sub et décode la charge utile base64.

        Structure d'entrée attendue :
        {
          "message": {"data": "<b64>", "messageId": "...", "publishTime": "..."},
          "subscription": "..."
        }
        """
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Corps JSON invalide reçu de Google Pub/Sub.",
            )

        message = body.get("message", {})
        subscription = body.get("subscription", "")
        message_id = message.get("messageId", message.get("message_id", ""))
        publish_time = message.get("publishTime", message.get("publish_time"))

        # Décode la charge utile base64
        raw_data_b64: str = message.get("data", "")
        decoded_data: dict[str, Any] = {}

        if raw_data_b64:
            try:
                padding = "=" * (4 - len(raw_data_b64) % 4)
                decoded_bytes = base64.urlsafe_b64decode(raw_data_b64 + padding)
                decoded_data = json.loads(decoded_bytes)
            except Exception as exc:
                logger.warning(
                    "gmail pubsub data base64 decode failed",
                    error=str(exc),
                    raw_preview=raw_data_b64[:50],
                )
                decoded_data = {"raw_b64": raw_data_b64}

        try:
            return GmailPubSubMessage(
                message_id=message_id,
                subscription=subscription,
                data=decoded_data,
                publish_time=publish_time,
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            )

    async def normalize(
        self, raw: GmailPubSubMessage, meta: dict[str, Any] | None = None
    ) -> NormalizedEvent:
        enriched_meta = {**(meta or {}), "pubsub_message_id": raw.message_id}
        return normalize(EventSource.GMAIL, raw, enriched_meta)


# ── Simulation ────────────────────────────────────────────────────────────────

def build_fake_gmail_notification(
    email_address: str = "user@example.com",
    history_id: str = "12345",
    message_id: str = "sim-msg-001",
) -> dict[str, Any]:
    """
    Génère un payload Pub/Sub Gmail simulé encodé en base64.
    Utilisé par la route POST /api/v1/triggers/gmail/simulate.
    """
    data_payload = {
        "emailAddress": email_address,
        "historyId": history_id,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(data_payload).encode()
    ).decode().rstrip("=")

    from datetime import datetime, timezone
    return {
        "message": {
            "data": encoded,
            "messageId": message_id,
            "publishTime": datetime.now(timezone.utc).isoformat(),
        },
        "subscription": f"projects/my-project/subscriptions/gmail-push-{email_address}",
    }


# Singleton réutilisable par les routes FastAPI
gmail_adapter = GmailAdapter()
