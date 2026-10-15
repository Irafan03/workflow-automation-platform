"""
orchestrator-service/app/queue/consumer.py
Consommateur Redis asynchrone basé sur BLPOP.

Responsabilités :
  - Maintenir une connexion Redis persistante.
  - Consommer en continu la file REDIS_EVENTS_QUEUE via BLPOP.
  - Désérialiser chaque message en NormalizedEvent.
  - Appeler le callback fourni (WorkflowRunner.handle_event) pour chaque message.
  - Gérer les erreurs de connexion avec retry exponentiel (tenacity).
  - S'arrêter proprement sur réception d'un signal d'arrêt (asyncio.Event).
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from redis.asyncio import Redis, from_url
from redis.exceptions import ConnectionError as RedisConnectionError, RedisError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
import logging

from app.core.config import settings
from app.schemas.schemas import NormalizedEvent

logger = structlog.get_logger(__name__)

# Type du callback : async fn(event) → None
EventHandler = Callable[[NormalizedEvent], Awaitable[None]]


class RedisConsumer:
    """
    Worker asyncio qui écoute une file Redis et dispatch les événements.

    Usage :
        consumer = RedisConsumer()
        await consumer.start(handler=runner.handle_event, stop_event=stop)
    """

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._connected = False

    # ── Connexion ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Établit la connexion Redis."""
        self._redis = from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        # ping pour vérifier la connexion dès le départ
        await self._redis.ping()
        self._connected = True
        logger.info(
            "redis consumer connected",
            queue=settings.REDIS_EVENTS_QUEUE,
        )

    async def close(self) -> None:
        """Ferme la connexion Redis proprement."""
        if self._redis:
            await self._redis.aclose()
            self._connected = False
            logger.info("redis consumer disconnected")

    async def ping(self) -> bool:
        """Vérifie la connectivité Redis (utilisé pour le health check)."""
        try:
            if self._redis:
                await self._redis.ping()
                return True
        except Exception:  # noqa: BLE001
            pass
        return False

    # ── Boucle principale ────────────────────────────────────────────────────

    async def start(
        self,
        handler: EventHandler,
        stop_event: asyncio.Event,
        semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        """
        Boucle de consommation principale.

        Args:
            handler:    Coroutine appelée pour chaque événement désérialisé.
            stop_event: asyncio.Event — levé pour arrêter proprement la boucle.
            semaphore:  Limite la concurrence (ORCHESTRATOR_CONCURRENCY).
        """
        if not self._connected:
            await self.connect()

        sem = semaphore or asyncio.Semaphore(settings.ORCHESTRATOR_CONCURRENCY)

        logger.info(
            "redis consumer loop started",
            queue=settings.REDIS_EVENTS_QUEUE,
            blpop_timeout=settings.REDIS_BLPOP_TIMEOUT,
            concurrency=settings.ORCHESTRATOR_CONCURRENCY,
        )

        while not stop_event.is_set():
            try:
                await self._poll_once(handler, sem)
            except RedisConnectionError as exc:
                logger.error("redis connection lost, reconnecting", error=str(exc))
                await self._reconnect_with_backoff()
            except asyncio.CancelledError:
                logger.info("redis consumer cancelled")
                break
            except Exception as exc:  # noqa: BLE001
                logger.error("unexpected consumer error", error=str(exc))
                await asyncio.sleep(1)

        logger.info("redis consumer loop stopped")

    async def _poll_once(
        self,
        handler: EventHandler,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """
        Fait un appel BLPOP bloquant avec timeout.
        Si un message est reçu, le traite de manière concurrente.
        """
        assert self._redis is not None

        result = await self._redis.blpop(
            settings.REDIS_EVENTS_QUEUE,
            timeout=settings.REDIS_BLPOP_TIMEOUT,
        )

        if result is None:
            # Timeout BLPOP — aucun message, on reboucle
            return

        _queue_name, raw_message = result

        event = self._deserialize(raw_message)
        if event is None:
            return

        # Lance le traitement en tâche asyncio pour ne pas bloquer le consumer
        asyncio.create_task(
            self._dispatch(event, handler, semaphore),
            name=f"exec-{event.event_id[:8]}",
        )

    async def _dispatch(
        self,
        event: NormalizedEvent,
        handler: EventHandler,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """Appelle le handler sous contrôle du sémaphore de concurrence."""
        async with semaphore:
            try:
                await handler(event)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "handler error",
                    event_id=event.event_id,
                    source=event.source,
                    error=str(exc),
                )

    @staticmethod
    def _deserialize(raw: str) -> NormalizedEvent | None:
        """Désérialise un message JSON en NormalizedEvent."""
        try:
            data: dict[str, Any] = json.loads(raw)
            return NormalizedEvent(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.error(
                "failed to deserialize redis message",
                error=str(exc),
                raw=raw[:200],
            )
            return None

    # ── Reconnexion avec backoff ──────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(RedisConnectionError),
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        reraise=True,
    )
    async def _reconnect_with_backoff(self) -> None:
        """Tente de se reconnecter à Redis avec backoff exponentiel."""
        self._connected = False
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:  # noqa: BLE001
                pass
        await self.connect()


# Singleton
redis_consumer = RedisConsumer()
