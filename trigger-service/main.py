"""
trigger-service/main.py
Point d'entrée principal du microservice trigger-service.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import Request, status

from app.api.v1 import triggers
from app.core.config import settings
from app.core.redis_client import close_redis, get_redis, ping_redis

logger = structlog.get_logger(__name__)


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise Redis au démarrage, ferme la connexion à l'arrêt."""
    logger.info("trigger-service starting", env=settings.ENVIRONMENT)

    # Vérifie la connexion Redis dès le démarrage
    redis_ok = await ping_redis()
    if not redis_ok:
        logger.error("redis not reachable on startup — events will fail to publish")
    else:
        logger.info(
            "redis connection established",
            queue=settings.REDIS_EVENTS_QUEUE,
        )

    yield  # ← l'application tourne ici

    await close_redis()
    logger.info("trigger-service shutdown complete")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Microservice de capture et normalisation d'événements externes. "
        "Supporte les webhooks génériques, Telegram Bot API et Gmail Pub/Sub."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ── Middlewares ───────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Gestionnaire d'erreurs global ─────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Erreur interne du serveur."},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], include_in_schema=False)
async def health_check() -> dict:
    """Health check Docker + load balancer avec état Redis."""
    redis_ok = await ping_redis()
    return {
        "status": "ok" if redis_ok else "degraded",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "redis": "connected" if redis_ok else "unreachable",
        "queue": settings.REDIS_EVENTS_QUEUE,
    }


app.include_router(triggers.router, prefix="/api/v1")
