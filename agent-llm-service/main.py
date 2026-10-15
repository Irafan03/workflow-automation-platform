"""
agent-llm-service/main.py
Point d'entrée principal du microservice agent-llm-service.

Responsabilités :
  - Initialise MLflow au démarrage (setup de l'expérience).
  - Monte le router d'inférence sous /api/v1.
  - Expose /health avec l'état du backend LLM et MLflow.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import inference
from app.core.config import settings
from app.tracking.mlflow_tracker import mlflow_tracker

logger = structlog.get_logger(__name__)


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise les ressources au démarrage, les libère à l'arrêt."""
    logger.info(
        "agent-llm-service starting",
        env=settings.ENVIRONMENT,
        llm_provider=settings.LLM_PROVIDER,
        mlflow_uri=settings.MLFLOW_TRACKING_URI,
    )

    # Connexion MLflow — configure le tracking URI et crée l'expérience
    try:
        mlflow_tracker.setup()
        logger.info(
            "mlflow initialized",
            experiment=settings.MLFLOW_EXPERIMENT_NAME,
        )
    except Exception as exc:  # noqa: BLE001
        # Non-fatal : le service reste opérationnel sans MLflow
        logger.error(
            "mlflow initialization failed — tracking will be disabled",
            error=str(exc),
        )

    yield  # ← l'application tourne ici

    logger.info("agent-llm-service shutdown complete")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Microservice cognitif de la plateforme d'automatisation. "
        "Reçoit le contexte d'exécution d'un agent, effectue l'inférence via LangChain "
        "(Ollama/Gemma ou OpenAI) et log automatiquement chaque run dans MLflow Tracking."
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


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"], include_in_schema=False)
async def health_check() -> dict:
    """
    Health check Docker + load balancer.
    Vérifie la connectivité MLflow et expose la config du provider LLM.
    """
    mlflow_status = await mlflow_tracker.health_check()

    overall = "ok" if mlflow_status["status"] == "connected" else "degraded"

    return {
        "status":      overall,
        "service":     settings.APP_NAME,
        "version":     settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "llm": {
            "provider": settings.LLM_PROVIDER,
            "model": (
                settings.OLLAMA_MODEL
                if settings.LLM_PROVIDER == "ollama"
                else settings.OPENAI_MODEL
            ),
        },
        "mlflow": mlflow_status,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(inference.router, prefix="/api/v1")
