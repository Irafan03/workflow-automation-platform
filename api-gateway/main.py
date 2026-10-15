"""
api-gateway/main.py
Point d'entrée principal du microservice api-gateway.
"""
import structlog
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import workflows
from app.core.config import settings
from app.db.database import engine, Base

logger = structlog.get_logger(__name__)


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise les ressources au démarrage, les libère à l'arrêt."""
    logger.info("api-gateway starting", env=settings.ENVIRONMENT)

    # Crée les tables si elles n'existent pas (dev only — en prod : Alembic)
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database tables synced (dev mode)")

    yield  # ← l'application tourne ici

    await engine.dispose()
    logger.info("api-gateway shutdown complete")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Point d'entrée REST de la plateforme d'automatisation de workflows.",
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

# Health check (utilisé par Docker + load balancer)
@app.get("/health", tags=["Health"], include_in_schema=False)
async def health_check() -> dict:
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


# API v1
app.include_router(workflows.router, prefix="/api/v1")
