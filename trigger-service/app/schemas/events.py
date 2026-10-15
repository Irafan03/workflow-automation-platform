"""
trigger-service/app/schemas/events.py
Schémas Pydantic v2 pour les événements bruts entrants et l'événement normalisé.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Sources d'événements connues ──────────────────────────────────────────────

class EventSource(str, Enum):
    WEBHOOK  = "webhook"
    TELEGRAM = "telegram"
    GMAIL    = "gmail"
    UNKNOWN  = "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# Événement normalisé — format canonique publié dans Redis
# ══════════════════════════════════════════════════════════════════════════════

class NormalizedEvent(BaseModel):
    """
    Représentation canonique d'un événement, quelle que soit sa source.
    C'est ce format qui est sérialisé en JSON et poussé dans la file Redis.
    """
    model_config = ConfigDict(use_enum_values=True)

    # Identifiant unique de l'événement (généré par le trigger-service)
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID v4 unique de l'événement",
    )

    # Source ayant produit l'événement
    source: EventSource = Field(..., description="Source de l'événement")

    # Timestamp ISO 8601 UTC du moment de réception
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Horodatage UTC ISO 8601 de la réception",
    )

    # Charge utile normalisée (contenu libre selon la source)
    payload: dict[str, Any] = Field(..., description="Contenu de l'événement")

    # Métadonnées techniques optionnelles (headers HTTP, IP, etc.)
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Métadonnées techniques optionnelles",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Payloads bruts entrants — un schéma par source
# ══════════════════════════════════════════════════════════════════════════════

class WebhookPayload(BaseModel):
    """Payload générique d'un webhook HTTP entrant."""
    event_type: str = Field(..., min_length=1, description="Type d'événement déclaré par l'expéditeur")
    data: dict[str, Any] = Field(default_factory=dict, description="Corps de l'événement")
    source_system: str | None = Field(default=None, description="Identifiant du système source (ex: github, stripe)")


# ── Telegram ──────────────────────────────────────────────────────────────────

class TelegramUser(BaseModel):
    id: int
    is_bot: bool = False
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str  # private | group | supergroup | channel
    title: str | None = None
    username: str | None = None
    first_name: str | None = None


class TelegramMessage(BaseModel):
    message_id: int
    from_: TelegramUser | None = Field(default=None, alias="from")
    chat: TelegramChat
    date: int  # Unix timestamp
    text: str | None = None
    caption: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class TelegramUpdate(BaseModel):
    """
    Update Telegram Bot API (subset des champs pertinents).
    Ref: https://core.telegram.org/bots/api#update
    """
    update_id: int
    message: TelegramMessage | None = None
    edited_message: TelegramMessage | None = None
    callback_query: dict[str, Any] | None = None


# ── Gmail ─────────────────────────────────────────────────────────────────────

class GmailPubSubMessage(BaseModel):
    """
    Message reçu via Google Cloud Pub/Sub (notification push Gmail).
    data est base64-encodé côté Google ; ici il est déjà décodé/parsé.
    """
    message_id: str
    subscription: str
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Corps du message Pub/Sub décodé (historyId, emailAddress…)",
    )
    publish_time: str | None = None


# ── Réponse API ───────────────────────────────────────────────────────────────

class TriggerResponse(BaseModel):
    """Réponse retournée au client après réception et publication d'un événement."""
    event_id: str
    source: str
    status: str = "queued"
    queue: str
    queue_length: int
