"""
trigger-service/app/api/v1/triggers.py
Routes FastAPI pour la réception des déclencheurs externes.

Endpoints :
  POST /api/v1/triggers/webhook          → webhook générique
  POST /api/v1/triggers/telegram         → update Telegram Bot API
  POST /api/v1/triggers/gmail            → notification push Gmail Pub/Sub
  POST /api/v1/triggers/webhook/simulate → simulation webhook (dev)
  POST /api/v1/triggers/telegram/simulate → simulation Telegram (dev)
  POST /api/v1/triggers/gmail/simulate   → simulation Gmail (dev)
"""
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, status

from app.adapters.gmail import build_fake_gmail_notification, gmail_adapter
from app.adapters.telegram import build_fake_telegram_update, telegram_adapter
from app.adapters.webhook import webhook_adapter
from app.core.config import settings
from app.core.redis_client import publish_event
from app.schemas.events import TriggerResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/triggers", tags=["Triggers"])


# ── Helper commun ─────────────────────────────────────────────────────────────

async def _publish_normalized(event_dict: dict[str, Any]) -> TriggerResponse:
    """Publie l'événement dans Redis et retourne la réponse API."""
    queue_length = await publish_event(event_dict)
    return TriggerResponse(
        event_id=event_dict["event_id"],
        source=event_dict["source"],
        status="queued",
        queue=settings.REDIS_EVENTS_QUEUE,
        queue_length=queue_length,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Webhook générique
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/webhook",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Recevoir un webhook générique",
    description=(
        "Reçoit n'importe quel webhook JSON, le normalise et le publie dans Redis. "
        "Signature optionnelle via header `X-Webhook-Signature: sha256=<hmac>`."
    ),
)
async def receive_webhook(request: Request) -> TriggerResponse:
    event = await webhook_adapter.process(request)
    logger.info("webhook received", event_id=event.event_id)
    return await _publish_normalized(event.model_dump())


# ══════════════════════════════════════════════════════════════════════════════
# Telegram
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/telegram",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Recevoir une mise à jour Telegram Bot API",
    description=(
        "Endpoint de webhook Telegram. "
        "Requiert le header `X-Telegram-Bot-Api-Secret-Token` si TELEGRAM_WEBHOOK_SECRET est défini."
    ),
)
async def receive_telegram(request: Request) -> TriggerResponse:
    event = await telegram_adapter.process(request)
    logger.info("telegram update received", event_id=event.event_id)
    return await _publish_normalized(event.model_dump())


# ══════════════════════════════════════════════════════════════════════════════
# Gmail (Pub/Sub push)
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/gmail",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Recevoir une notification Gmail via Pub/Sub",
    description=(
        "Endpoint de push subscription Google Pub/Sub pour Gmail. "
        "Vérification via query param `?token=<GMAIL_WEBHOOK_TOKEN>`."
    ),
)
async def receive_gmail(request: Request) -> TriggerResponse:
    event = await gmail_adapter.process(request)
    logger.info("gmail notification received", event_id=event.event_id)
    return await _publish_normalized(event.model_dump())


# ══════════════════════════════════════════════════════════════════════════════
# Routes de simulation (dev / staging uniquement)
# ══════════════════════════════════════════════════════════════════════════════

def _check_dev_mode() -> None:
    """Lève 403 si l'environnement n'est pas development ou staging."""
    if settings.ENVIRONMENT not in ("development", "staging"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les routes de simulation ne sont disponibles qu'en développement.",
        )


@router.post(
    "/webhook/simulate",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[DEV] Simuler un webhook entrant",
    tags=["Simulation"],
)
async def simulate_webhook(body: dict[str, Any]) -> TriggerResponse:
    """Injecte un payload webhook fictif sans passer par la vérification de signature."""
    _check_dev_mode()
    from app.schemas.events import WebhookPayload
    from app.normalizer import normalize
    from app.schemas.events import EventSource

    payload = WebhookPayload(
        event_type=body.get("event_type", "simulation"),
        data=body.get("data", {}),
        source_system=body.get("source_system", "simulator"),
    )
    event = normalize(EventSource.WEBHOOK, payload, {"simulated": True})
    logger.info("webhook simulation triggered", event_id=event.event_id)
    return await _publish_normalized(event.model_dump())


@router.post(
    "/telegram/simulate",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[DEV] Simuler une mise à jour Telegram",
    tags=["Simulation"],
)
async def simulate_telegram(
    chat_id: int = 123456789,
    text: str = "Message de simulation Telegram",
) -> TriggerResponse:
    """Génère et traite un update Telegram simulé."""
    _check_dev_mode()
    from app.schemas.events import TelegramUpdate
    from app.normalizer import normalize
    from app.schemas.events import EventSource

    fake = build_fake_telegram_update(chat_id=chat_id, text=text)
    update = TelegramUpdate(**fake)
    event = normalize(EventSource.TELEGRAM, update, {"simulated": True})
    logger.info("telegram simulation triggered", event_id=event.event_id)
    return await _publish_normalized(event.model_dump())


@router.post(
    "/gmail/simulate",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="[DEV] Simuler une notification Gmail",
    tags=["Simulation"],
)
async def simulate_gmail(
    email_address: str = "user@example.com",
    history_id: str = "99999",
) -> TriggerResponse:
    """Génère et traite une notification Gmail Pub/Sub simulée."""
    _check_dev_mode()
    import httpx
    from app.schemas.events import GmailPubSubMessage, EventSource
    from app.normalizer import normalize
    import base64, json

    fake_body = build_fake_gmail_notification(
        email_address=email_address, history_id=history_id
    )
    # Décode directement le payload sans passer par HTTP
    msg = fake_body["message"]
    raw_b64 = msg["data"]
    padding = "=" * (4 - len(raw_b64) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(raw_b64 + padding))

    notification = GmailPubSubMessage(
        message_id=msg["messageId"],
        subscription=fake_body["subscription"],
        data=decoded,
        publish_time=msg["publishTime"],
    )
    event = normalize(EventSource.GMAIL, notification, {"simulated": True})
    logger.info("gmail simulation triggered", event_id=event.event_id)
    return await _publish_normalized(event.model_dump())
