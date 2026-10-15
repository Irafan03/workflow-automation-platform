"""
trigger-service/app/normalizer.py
Fonction de normalisation : transforme tout événement brut en NormalizedEvent canonique.
"""
import base64
import json
from datetime import datetime, timezone
from typing import Any

import structlog

from app.schemas.events import (
    EventSource,
    GmailPubSubMessage,
    NormalizedEvent,
    TelegramUpdate,
    WebhookPayload,
)

logger = structlog.get_logger(__name__)


# ── Normalizers par source ────────────────────────────────────────────────────

def normalize_webhook(
    raw: WebhookPayload,
    meta: dict[str, Any] | None = None,
) -> NormalizedEvent:
    """
    Normalise un webhook générique.

    Le payload canonique contient :
    - event_type : type déclaré par l'expéditeur
    - source_system : système source optionnel
    - data : corps brut de l'événement
    """
    return NormalizedEvent(
        source=EventSource.WEBHOOK,
        payload={
            "event_type": raw.event_type,
            "source_system": raw.source_system,
            "data": raw.data,
        },
        meta=meta or {},
    )


def normalize_telegram(
    update: TelegramUpdate,
    meta: dict[str, Any] | None = None,
) -> NormalizedEvent:
    """
    Normalise une mise à jour Telegram Bot API.

    Extrait le message le plus pertinent (message > edited_message > callback_query)
    et construit un payload unifié.
    """
    # Détermine le message principal
    msg = update.message or update.edited_message
    is_edited = update.edited_message is not None and update.message is None

    if msg:
        # Convertit le timestamp Unix en ISO 8601 UTC
        msg_timestamp = datetime.fromtimestamp(msg.date, tz=timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "update_id": update.update_id,
            "event_type": "edited_message" if is_edited else "message",
            "message_id": msg.message_id,
            "chat_id": msg.chat.id,
            "chat_type": msg.chat.type,
            "text": msg.text or msg.caption,
            "sender": {
                "id": msg.from_.id if msg.from_ else None,
                "username": msg.from_.username if msg.from_ else None,
                "first_name": msg.from_.first_name if msg.from_ else None,
                "is_bot": msg.from_.is_bot if msg.from_ else False,
            },
            "message_timestamp": msg_timestamp,
        }
    elif update.callback_query:
        payload = {
            "update_id": update.update_id,
            "event_type": "callback_query",
            "callback_data": update.callback_query,
        }
    else:
        # Update non reconnu — on préserve le brut
        payload = {
            "update_id": update.update_id,
            "event_type": "unknown",
            "raw": update.model_dump(),
        }

    return NormalizedEvent(
        source=EventSource.TELEGRAM,
        payload=payload,
        meta=meta or {},
    )


def normalize_gmail(
    notification: GmailPubSubMessage,
    meta: dict[str, Any] | None = None,
) -> NormalizedEvent:
    """
    Normalise une notification push Gmail (Pub/Sub).

    Le champ `data` peut contenir du JSON base64 en provenance de Google ;
    si c'est le cas on le décode, sinon on utilise le dict déjà parsé.
    """
    decoded_data: dict[str, Any] = notification.data

    # Tentative de décodage base64 si la valeur est une chaîne
    if isinstance(decoded_data.get("raw_b64"), str):
        try:
            raw_bytes = base64.urlsafe_b64decode(
                decoded_data["raw_b64"] + "=="  # padding safety
            )
            decoded_data = {**decoded_data, "decoded": json.loads(raw_bytes)}
        except Exception as exc:
            logger.warning("gmail base64 decode failed", error=str(exc))

    return NormalizedEvent(
        source=EventSource.GMAIL,
        payload={
            "event_type": "gmail_notification",
            "message_id": notification.message_id,
            "subscription": notification.subscription,
            "publish_time": notification.publish_time,
            "data": decoded_data,
        },
        meta=meta or {},
    )


# ── Dispatcher principal ──────────────────────────────────────────────────────

def normalize(
    source: EventSource,
    raw_data: Any,
    meta: dict[str, Any] | None = None,
) -> NormalizedEvent:
    """
    Point d'entrée unique de normalisation.
    Dispatche vers le normalizer approprié selon la source.

    Args:
        source:   Source de l'événement (EventSource enum).
        raw_data: Objet Pydantic déjà validé par le schéma de la source.
        meta:     Métadonnées techniques additionnelles (headers, IP…).

    Returns:
        NormalizedEvent prêt à être sérialisé et publié dans Redis.
    """
    logger.debug("normalizing event", source=source)

    match source:
        case EventSource.WEBHOOK:
            return normalize_webhook(raw_data, meta)
        case EventSource.TELEGRAM:
            return normalize_telegram(raw_data, meta)
        case EventSource.GMAIL:
            return normalize_gmail(raw_data, meta)
        case _:
            # Fallback : encapsule le brut sans transformation
            logger.warning("unknown source, using raw fallback", source=source)
            return NormalizedEvent(
                source=EventSource.UNKNOWN,
                payload={"raw": raw_data} if not isinstance(raw_data, dict) else raw_data,
                meta=meta or {},
            )
