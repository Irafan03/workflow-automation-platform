"""
orchestrator-service/main.py
Point d'entrée principal du microservice orchestrator-service.

Architecture :
  - Worker asyncio principal : consomme Redis (BLPOP) et exécute les workflows.
  - Serveur HTTP minimal (aiohttp-free, stdlib uniquement) pour le health check
    Docker / load balancer sur le port HEALTH_PORT (8003).
  - Démarrage et arrêt propres via asyncio.Event + signal handlers.
"""
from __future__ import annotations

import asyncio
import json
import logging
import signal
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import structlog

from app.clients.agent_llm import agent_llm_client
from app.core.config import settings
from app.execution.runner import workflow_runner
from app.queue.consumer import redis_consumer

# ── Logging ───────────────────────────────────────────────────────────────────
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    ),
)
logger = structlog.get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Health HTTP server (stdlib, thread séparé)
# ══════════════════════════════════════════════════════════════════════════════

_health_status: dict = {"status": "starting"}


class _HealthHandler(BaseHTTPRequestHandler):
    """Handler HTTP minimaliste pour /health."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            body = json.dumps(_health_status).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:  # type: ignore[override]
        # Silences the default HTTP access log
        pass


def _start_health_server(port: int) -> HTTPServer:
    """Démarre le serveur HTTP de health dans un thread daemon."""
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True, name="health-http")
    thread.start()
    logger.info("health server started", port=port)
    return server


# ══════════════════════════════════════════════════════════════════════════════
# Initialisation et arrêt des ressources
# ══════════════════════════════════════════════════════════════════════════════

async def startup() -> None:
    """Initialise toutes les ressources du worker."""
    logger.info(
        "orchestrator-service starting",
        env=settings.ENVIRONMENT,
        redis_queue=settings.REDIS_EVENTS_QUEUE,
        agent_llm_url=settings.AGENT_LLM_URL,
        concurrency=settings.ORCHESTRATOR_CONCURRENCY,
    )

    # Connexion Redis
    await redis_consumer.connect()

    # Client HTTP vers agent-llm-service
    await agent_llm_client.start()

    # Mise à jour du statut health
    redis_ok = await redis_consumer.ping()
    agent_ok = await agent_llm_client.health()
    _health_status.update({
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "redis": "connected" if redis_ok else "unreachable",
        "agent_llm": "reachable" if agent_ok else "unreachable",
        "queue": settings.REDIS_EVENTS_QUEUE,
        "concurrency": settings.ORCHESTRATOR_CONCURRENCY,
    })

    logger.info(
        "orchestrator-service ready",
        redis=_health_status["redis"],
        agent_llm=_health_status["agent_llm"],
    )


async def shutdown() -> None:
    """Ferme toutes les ressources proprement."""
    logger.info("orchestrator-service shutting down")
    _health_status["status"] = "stopping"

    await redis_consumer.close()
    await agent_llm_client.close()

    logger.info("orchestrator-service stopped")


# ══════════════════════════════════════════════════════════════════════════════
# Boucle principale
# ══════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    """
    Boucle principale du worker :
      1. Démarre le serveur health HTTP.
      2. Initialise les ressources.
      3. Lance le consommateur Redis jusqu'au signal d'arrêt.
      4. Nettoie les ressources.
    """
    # Health HTTP dans un thread daemon
    _start_health_server(settings.HEALTH_PORT)

    # Signal d'arrêt propre (SIGTERM / SIGINT)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        logger.info("shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows ne supporte pas add_signal_handler
            signal.signal(sig, lambda s, f: _signal_handler())

    # Initialisation
    await startup()

    # Sémaphore de concurrence partagé
    semaphore = asyncio.Semaphore(settings.ORCHESTRATOR_CONCURRENCY)

    try:
        # Boucle de consommation Redis (bloque jusqu'à stop_event)
        await redis_consumer.start(
            handler=workflow_runner.handle_event,
            stop_event=stop_event,
            semaphore=semaphore,
        )
    finally:
        await shutdown()


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    asyncio.run(main())
