"""
agent-llm-service/app/llm/client.py
Client LLM unifié basé sur LangChain.

Supporte :
  - Ollama (ChatOllama) — modèle local conteneurisé (ex: gemma:2b)
  - OpenAI (ChatOpenAI)  — API distante (fallback cloud)

Le client est instancié en fonction du provider résolu à partir de la requête
ou de la configuration par défaut.
"""
from __future__ import annotations

import time
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.schemas.schemas import InferenceRequest, LLMProvider, TokenUsage

logger = structlog.get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Résultat intermédiaire d'inférence
# ══════════════════════════════════════════════════════════════════════════════

class LLMResult:
    """Encapsule la réponse brute du modèle avec les métriques associées."""

    def __init__(
        self,
        content: str,
        provider: LLMProvider,
        model: str,
        temperature: float,
        token_usage: TokenUsage,
        latency_ms: float,
    ) -> None:
        self.content = content
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.token_usage = token_usage
        self.latency_ms = latency_ms


# ══════════════════════════════════════════════════════════════════════════════
# Factory LangChain
# ══════════════════════════════════════════════════════════════════════════════

def _build_chat_model(
    provider: LLMProvider,
    model: str,
    temperature: float,
    max_tokens: int,
) -> BaseChatModel:
    """
    Instancie le modèle LangChain approprié selon le provider.

    Raises:
        ValueError: Si le provider est inconnu.
        ImportError: Si les dépendances nécessaires ne sont pas installées.
    """
    if provider == LLMProvider.OLLAMA:
        from langchain_community.chat_models import ChatOllama  # type: ignore[import-untyped]

        return ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=model,
            temperature=temperature,
            num_predict=max_tokens,
            timeout=settings.LLM_REQUEST_TIMEOUT,
        )

    if provider == LLMProvider.OPENAI:
        from langchain_openai import ChatOpenAI  # type: ignore[import-untyped]

        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY n'est pas définie. "
                "Configurez-la dans .env ou utilisez provider=ollama."
            )
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=settings.LLM_REQUEST_TIMEOUT,
        )

    raise ValueError(f"Provider LLM inconnu : {provider!r}")


# ══════════════════════════════════════════════════════════════════════════════
# Conversion de l'historique de conversation
# ══════════════════════════════════════════════════════════════════════════════

def _build_messages(
    system_prompt: str,
    conversation_history: list[dict[str, str]],
    user_message: str,
) -> list[SystemMessage | HumanMessage | AIMessage]:
    """
    Construit la liste de messages LangChain à partir du contexte de la requête.

    Le format attendu de conversation_history :
      [{"role": "user"|"assistant", "content": "..."}]
    """
    messages: list[Any] = [SystemMessage(content=system_prompt)]

    for turn in conversation_history:
        role = turn.get("role", "").lower()
        content = turn.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            logger.warning("unknown role in conversation_history, skipping", role=role)

    messages.append(HumanMessage(content=user_message))
    return messages


# ══════════════════════════════════════════════════════════════════════════════
# Extraction des token usage
# ══════════════════════════════════════════════════════════════════════════════

def _extract_token_usage(ai_message: AIMessage) -> TokenUsage:
    """
    Extrait les informations de token depuis les métadonnées du message LangChain.
    Les champs varient selon le provider — on normalise ici.
    """
    usage_meta: dict[str, Any] = {}

    # OpenAI : response_metadata.token_usage ou usage_metadata
    if hasattr(ai_message, "response_metadata"):
        meta = ai_message.response_metadata or {}
        usage_meta = meta.get("token_usage") or meta.get("usage") or {}

    # LangChain usage_metadata (LangChain >= 0.2)
    if not usage_meta and hasattr(ai_message, "usage_metadata") and ai_message.usage_metadata:
        um = ai_message.usage_metadata
        return TokenUsage(
            prompt_tokens=um.get("input_tokens", 0),
            completion_tokens=um.get("output_tokens", 0),
            total_tokens=um.get("total_tokens", 0),
        )

    return TokenUsage(
        prompt_tokens=usage_meta.get("prompt_tokens", 0),
        completion_tokens=usage_meta.get("completion_tokens", 0),
        total_tokens=usage_meta.get("total_tokens", 0),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Client principal
# ══════════════════════════════════════════════════════════════════════════════

class LLMClient:
    """
    Client LLM asynchrone unifié.
    Résout le provider / modèle, construit les messages et appelle le LLM.
    """

    def _resolve_params(
        self, request: InferenceRequest
    ) -> tuple[LLMProvider, str, float, int]:
        """Résout les paramètres LLM en fusionnant requête et config."""
        provider = request.provider or LLMProvider(settings.LLM_PROVIDER)
        temperature = (
            request.temperature
            if request.temperature is not None
            else settings.LLM_DEFAULT_TEMPERATURE
        )
        max_tokens = (
            request.max_tokens
            if request.max_tokens is not None
            else settings.LLM_DEFAULT_MAX_TOKENS
        )

        # Modèle par défaut selon le provider
        if request.model:
            model = request.model
        elif provider == LLMProvider.OLLAMA:
            model = settings.OLLAMA_MODEL
        else:
            model = settings.OPENAI_MODEL

        return provider, model, temperature, max_tokens

    @retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def infer(
        self,
        request: InferenceRequest,
        system_prompt: str,
    ) -> LLMResult:
        """
        Effectue l'inférence LLM de manière asynchrone.

        Args:
            request:       Requête d'inférence complète.
            system_prompt: System prompt déjà résolu par PromptManager.

        Returns:
            LLMResult avec le contenu, les métriques et les informations d'usage.

        Raises:
            TimeoutError:    Si le modèle ne répond pas dans LLM_REQUEST_TIMEOUT.
            ConnectionError: Si le backend LLM est inaccessible.
            RuntimeError:    Pour toute autre erreur d'inférence.
        """
        provider, model, temperature, max_tokens = self._resolve_params(request)

        logger.info(
            "starting llm inference",
            provider=provider.value,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            agent_id=request.agent_id,
        )

        chat_model = _build_chat_model(provider, model, temperature, max_tokens)
        messages = _build_messages(
            system_prompt,
            request.conversation_history,
            request.user_message,
        )

        t_start = time.perf_counter()
        try:
            # LangChain ainvoke est asynchrone
            ai_message: AIMessage = await chat_model.ainvoke(messages)  # type: ignore[assignment]
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            logger.error(
                "llm inference failed",
                provider=provider.value,
                model=model,
                latency_ms=round(elapsed_ms, 2),
                error=str(exc),
                agent_id=request.agent_id,
            )
            raise RuntimeError(f"Erreur d'inférence LLM ({provider.value}/{model}): {exc}") from exc

        latency_ms = (time.perf_counter() - t_start) * 1000
        token_usage = _extract_token_usage(ai_message)

        logger.info(
            "llm inference complete",
            provider=provider.value,
            model=model,
            latency_ms=round(latency_ms, 2),
            total_tokens=token_usage.total_tokens,
            agent_id=request.agent_id,
        )

        return LLMResult(
            content=str(ai_message.content),
            provider=provider,
            model=model,
            temperature=temperature,
            token_usage=token_usage,
            latency_ms=round(latency_ms, 2),
        )


# Singleton
llm_client = LLMClient()
