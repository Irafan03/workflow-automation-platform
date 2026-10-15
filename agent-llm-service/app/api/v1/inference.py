"""
agent-llm-service/app/api/v1/inference.py
Routes FastAPI pour le service d'inférence LLM.

Endpoints :
  POST /api/v1/inference         → inférence principale
  POST /api/v1/inference/stream  → inférence en streaming SSE (dev)
  GET  /api/v1/inference/prompts → liste des templates de prompts disponibles
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator

import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.llm.client import llm_client
from app.prompts.manager import prompt_manager
from app.schemas.schemas import (
    InferenceRequest,
    InferenceResponse,
    LLMProvider,
    TokenUsage,
)
from app.tracking.mlflow_tracker import mlflow_tracker
from app.core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/inference", tags=["Inference"])


# ══════════════════════════════════════════════════════════════════════════════
# POST /inference — Inférence principale
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "",
    response_model=InferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Effectuer une inférence LLM",
    description=(
        "Reçoit le contexte d'exécution d'un agent, construit dynamiquement le "
        "system prompt, appelle le modèle LLM configuré et log automatiquement "
        "les hyperparamètres, métriques et métadonnées dans MLflow. "
        "Retourne la réponse enrichie du modèle avec le `mlflow_run_id`."
    ),
    responses={
        200: {"description": "Inférence réussie."},
        422: {"description": "Corps de requête invalide."},
        503: {"description": "Backend LLM inaccessible."},
        500: {"description": "Erreur interne."},
    },
)
async def run_inference(request: InferenceRequest) -> InferenceResponse:
    """
    Pipeline d'inférence complet :
      1. Résolution du system prompt via PromptManager.
      2. Inférence LLM via LLMClient (LangChain).
      3. Logging MLflow (non-bloquant, en parallèle).
      4. Construction et renvoi de InferenceResponse.
    """
    log = logger.bind(
        agent_id=request.agent_id,
        workflow_run_id=request.workflow_run_id,
    )
    log.info("inference request received")

    # ── 1. System prompt ──────────────────────────────────────────────────────
    system_prompt, raw_template = prompt_manager.resolve(
        request.prompt_override,
        request.tools,
    )
    log.debug("system prompt resolved", prompt_len=len(system_prompt))

    # ── 2. Inférence LLM ──────────────────────────────────────────────────────
    try:
        result = await llm_client.infer(request, system_prompt)
    except RuntimeError as exc:
        log.error("llm inference error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log.error("unexpected inference error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur inattendue lors de l'inférence: {exc}",
        ) from exc

    # ── 3. MLflow tracking (non-bloquant) ─────────────────────────────────────
    mlflow_run_id = await mlflow_tracker.log_inference(request, result, raw_template)

    # ── 4. Réponse ────────────────────────────────────────────────────────────
    log.info(
        "inference complete",
        provider=result.provider.value,
        model=result.model,
        latency_ms=result.latency_ms,
        total_tokens=result.token_usage.total_tokens,
        mlflow_run_id=mlflow_run_id,
    )

    return InferenceResponse(
        agent_id=request.agent_id,
        workflow_run_id=request.workflow_run_id,
        content=result.content,
        provider=result.provider,
        model=result.model,
        temperature=result.temperature,
        token_usage=result.token_usage,
        latency_ms=result.latency_ms,
        mlflow_run_id=mlflow_run_id,
        mlflow_experiment_name=settings.MLFLOW_EXPERIMENT_NAME,
    )


# ══════════════════════════════════════════════════════════════════════════════
# POST /inference/stream — Streaming SSE (dev / staging uniquement)
# ══════════════════════════════════════════════════════════════════════════════

async def _stream_tokens(
    request: InferenceRequest,
    system_prompt: str,
) -> AsyncGenerator[str, None]:
    """
    Génère les tokens SSE en streaming via LangChain astream.
    Format : `data: <token>\n\n` (Server-Sent Events).
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        from langchain_community.chat_models import ChatOllama  # type: ignore[import-untyped]
        from app.llm.client import _build_chat_model, _build_messages

        # Résolution des paramètres
        provider_val = request.provider or LLMProvider(settings.LLM_PROVIDER)
        temperature = request.temperature if request.temperature is not None else settings.LLM_DEFAULT_TEMPERATURE
        max_tokens = request.max_tokens if request.max_tokens is not None else settings.LLM_DEFAULT_MAX_TOKENS
        model = request.model or (
            settings.OLLAMA_MODEL if provider_val.value == "ollama" else settings.OPENAI_MODEL
        )

        chat_model = _build_chat_model(provider_val, model, temperature, max_tokens)
        messages = _build_messages(system_prompt, request.conversation_history, request.user_message)

        async for chunk in chat_model.astream(messages):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if token:
                yield f"data: {token}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as exc:
        yield f"data: [ERROR] {exc}\n\n"


@router.post(
    "/stream",
    summary="[DEV] Inférence LLM en streaming (SSE)",
    description=(
        "Retourne les tokens du modèle au fil de la génération via Server-Sent Events. "
        "Disponible uniquement en développement et staging. "
        "**Note** : Le tracking MLflow n'est pas effectué sur les appels en streaming."
    ),
    tags=["Streaming"],
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "Stream de tokens SSE."},
        403: {"description": "Non disponible hors développement."},
    },
)
async def stream_inference(request: InferenceRequest) -> StreamingResponse:
    """Stream les tokens générés via SSE."""
    if settings.ENVIRONMENT not in ("development", "staging"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le streaming n'est disponible qu'en développement.",
        )

    system_prompt, _ = prompt_manager.resolve(request.prompt_override, request.tools)

    return StreamingResponse(
        _stream_tokens(request, system_prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # désactive le buffering nginx
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# GET /inference/prompts — Liste des templates disponibles
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/prompts",
    summary="Lister les templates de prompts disponibles",
    description="Retourne les identifiants des templates de system prompts enregistrés.",
    response_model=dict[str, list[str]],
)
async def list_prompt_templates() -> dict[str, list[str]]:
    """Retourne la liste des template_id utilisables dans PromptOverride."""
    return {"templates": prompt_manager.list_templates()}
