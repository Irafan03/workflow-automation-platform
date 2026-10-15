"""
orchestrator-service/app/clients/agent_llm.py
Client HTTP async vers l'agent-llm-service.

Envoie les requêtes d'inférence LLM et retourne la réponse structurée,
incluant le mlflow_run_id pour traçabilité.
"""
from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = structlog.get_logger(__name__)


# ── Schémas légers (évite de dépendre du package agent-llm-service) ───────────

class AgentInferenceRequest:
    """Paramètres d'une requête d'inférence vers l'agent-llm-service."""

    def __init__(
        self,
        agent_id: str,
        user_message: str,
        workflow_run_id: str | None = None,
        system_prompt: str | None = None,
        model_provider: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[str] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.user_message = user_message
        self.workflow_run_id = workflow_run_id
        self.system_prompt = system_prompt
        self.model_provider = model_provider
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools = tools or []
        self.conversation_history = conversation_history or []
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "agent_id": self.agent_id,
            "user_message": self.user_message,
            "tools": self.tools,
            "conversation_history": self.conversation_history,
            "metadata": self.metadata,
        }
        if self.workflow_run_id:
            body["workflow_run_id"] = self.workflow_run_id
        if self.system_prompt:
            body["prompt_override"] = {"system_prompt": self.system_prompt}
        if self.model_provider:
            body["provider"] = self.model_provider
        if self.model_name:
            body["model"] = self.model_name
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if self.max_tokens is not None:
            body["max_tokens"] = self.max_tokens
        return body


class AgentInferenceResponse:
    """Réponse désérialisée de l'agent-llm-service."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.content: str = data.get("content", "")
        self.provider: str = data.get("provider", "unknown")
        self.model: str = data.get("model", "unknown")
        self.temperature: float = data.get("temperature", 0.7)
        self.latency_ms: float = data.get("latency_ms", 0.0)
        self.mlflow_run_id: str = data.get("mlflow_run_id", "")
        self.mlflow_experiment_name: str = data.get("mlflow_experiment_name", "")
        token_usage = data.get("token_usage", {})
        self.prompt_tokens: int = token_usage.get("prompt_tokens", 0)
        self.completion_tokens: int = token_usage.get("completion_tokens", 0)
        self.total_tokens: int = token_usage.get("total_tokens", 0)


# ── Client HTTP ───────────────────────────────────────────────────────────────

class AgentLLMClient:
    """
    Client HTTP async vers l'agent-llm-service.
    Gère le cycle de vie du client httpx et les retries.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Initialise le client HTTP (appelé au démarrage du worker)."""
        self._client = httpx.AsyncClient(
            base_url=settings.AGENT_LLM_URL,
            timeout=httpx.Timeout(
                connect=10.0,
                read=float(settings.AGENT_LLM_TIMEOUT),
                write=10.0,
                pool=5.0,
            ),
            headers={"Content-Type": "application/json"},
        )
        logger.info("agent-llm client initialized", base_url=settings.AGENT_LLM_URL)

    async def close(self) -> None:
        """Ferme le client HTTP proprement."""
        if self._client:
            await self._client.aclose()
            logger.info("agent-llm client closed")

    async def health(self) -> bool:
        """Vérifie que l'agent-llm-service est joignable."""
        try:
            assert self._client is not None
            resp = await self._client.get("/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    @retry(
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def infer(
        self,
        request: AgentInferenceRequest,
    ) -> AgentInferenceResponse:
        """
        Envoie une requête d'inférence à l'agent-llm-service.

        Args:
            request: Paramètres de la requête d'inférence.

        Returns:
            AgentInferenceResponse avec le contenu et le mlflow_run_id.

        Raises:
            httpx.HTTPStatusError: Si le service retourne une erreur 4xx/5xx.
            httpx.TimeoutException: Si le timeout est dépassé.
            RuntimeError: Pour toute autre erreur.
        """
        assert self._client is not None, "Client non initialisé — appelez start() d'abord"

        payload = request.to_dict()
        log = logger.bind(
            agent_id=request.agent_id,
            workflow_run_id=request.workflow_run_id,
        )
        log.info("calling agent-llm-service", provider=request.model_provider)

        try:
            response = await self._client.post(
                "/api/v1/inference",
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            log.error(
                "agent-llm-service returned error",
                status_code=exc.response.status_code,
                detail=exc.response.text[:300],
            )
            raise RuntimeError(
                f"agent-llm-service error {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            log.error("agent-llm-service unreachable", error=str(exc))
            raise

        data = response.json()
        result = AgentInferenceResponse(data)

        log.info(
            "agent-llm-service response received",
            latency_ms=result.latency_ms,
            total_tokens=result.total_tokens,
            mlflow_run_id=result.mlflow_run_id,
        )
        return result


# Singleton
agent_llm_client = AgentLLMClient()
