"""
trigger-service/app/core/redis_client.py
Client Redis async — connexion singleton + publisher d'événements.
"""
import json
import structlog
from typing import Any

import redis.asyncio as aioredis
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ── Singleton de connexion ────────────────────────────────────────────────────
_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Retourne le client Redis singleton, en le créant si nécessaire."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        logger.info("redis client initialized", url=settings.REDIS_URL.split("@")[-1])
    return _redis_client


async def close_redis() -> None:
    """Ferme proprement la connexion Redis (appelé au shutdown)."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("redis connection closed")


# ── Publisher ─────────────────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type(aioredis.RedisError),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def publish_event(event: dict[str, Any], queue: str | None = None) -> int:
    """
    Pousse un événement JSON sérialisé dans une liste Redis (RPUSH).
    L'orchestrateur consommera via BLPOP depuis la gauche.

    Args:
        event:  Dictionnaire représentant l'événement normalisé.
        queue:  Nom de la file (défaut : REDIS_EVENTS_QUEUE depuis config).

    Returns:
        Longueur de la file après insertion.
    """
    target_queue = queue or settings.REDIS_EVENTS_QUEUE
    client = await get_redis()

    payload = json.dumps(event, ensure_ascii=False, default=str)
    queue_length: int = await client.rpush(target_queue, payload)

    logger.info(
        "event published to redis",
        queue=target_queue,
        event_id=event.get("event_id"),
        source=event.get("source"),
        queue_length=queue_length,
    )
    return queue_length


async def ping_redis() -> bool:
    """Vérifie que Redis est joignable (utilisé dans le health check)."""
    try:
        client = await get_redis()
        return await client.ping()
    except Exception as exc:
        logger.warning("redis ping failed", error=str(exc))
        return False
