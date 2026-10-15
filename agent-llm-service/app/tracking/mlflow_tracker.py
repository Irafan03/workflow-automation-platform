"""
agent-llm-service/app/tracking/mlflow_tracker.py
Intégration MLflow Tracking pour le logging automatique des inférences LLM.

Pour chaque inférence, un run MLflow est ouvert et log automatiquement :
  Params  : provider, model, temperature, max_tokens, prompt_template
  Metrics : latency_ms, prompt_tokens, completion_tokens, total_tokens
  Tags    : agent_id, workflow_run_id, environment, service
"""
from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import mlflow
import structlog

from app.core.config import settings
from app.llm.client import LLMResult
from app.schemas.schemas import InferenceRequest, TokenUsage

logger = structlog.get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# MLflowTracker
# ══════════════════════════════════════════════════════════════════════════════

class MLflowTracker:
    """
    Wrappeur autour du SDK MLflow pour le logging structuré des inférences.

    Les opérations MLflow sont bloquantes (SDK synchrone) ; on les exécute
    dans un thread pool via asyncio.to_thread pour ne pas bloquer la boucle
    d'événements FastAPI.
    """

    def __init__(self) -> None:
        self._initialized = False

    def setup(self) -> None:
        """
        Configure le tracking URI et crée/récupère l'expérience MLflow.
        Appelé une seule fois au démarrage de l'application (lifespan).
        """
        if self._initialized:
            return

        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)

        # Crée l'expérience si elle n'existe pas
        experiment = mlflow.get_experiment_by_name(settings.MLFLOW_EXPERIMENT_NAME)
        if experiment is None:
            mlflow.create_experiment(settings.MLFLOW_EXPERIMENT_NAME)
            logger.info(
                "mlflow experiment created",
                experiment=settings.MLFLOW_EXPERIMENT_NAME,
            )
        else:
            logger.info(
                "mlflow experiment found",
                experiment=settings.MLFLOW_EXPERIMENT_NAME,
                experiment_id=experiment.experiment_id,
            )

        mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)
        self._initialized = True

    # ── Logging synchrone (exécuté dans un thread) ────────────────────────────

    def _log_run_sync(
        self,
        request: InferenceRequest,
        result: LLMResult,
        raw_prompt_template: str,
    ) -> str:
        """
        Ouvre un run MLflow, log tous les artefacts et retourne le run_id.
        Cette méthode est synchrone et doit être appelée via asyncio.to_thread.
        """
        with mlflow.start_run() as run:
            # ── Hyperparamètres ────────────────────────────────────────────
            mlflow.log_params({
                "provider":         result.provider.value,
                "model":            result.model,
                "temperature":      result.temperature,
                "max_tokens":       request.max_tokens or settings.LLM_DEFAULT_MAX_TOKENS,
                "tools_enabled":    ",".join(t.value for t in request.tools) if request.tools else "none",
            })

            # ── Template du system prompt ──────────────────────────────────
            # On tronque à 500 chars pour rester dans les limites MLflow (250 par défaut)
            mlflow.log_param(
                "prompt_template",
                (raw_prompt_template[:497] + "...") if len(raw_prompt_template) > 500 else raw_prompt_template,
            )

            # ── Métriques ──────────────────────────────────────────────────
            mlflow.log_metrics({
                "latency_ms":          result.latency_ms,
                "prompt_tokens":       float(result.token_usage.prompt_tokens),
                "completion_tokens":   float(result.token_usage.completion_tokens),
                "total_tokens":        float(result.token_usage.total_tokens),
            })

            # ── Tags de contexte ───────────────────────────────────────────
            tags: dict[str, str] = {
                "agent_id":           request.agent_id,
                "environment":        settings.ENVIRONMENT,
                "service":            settings.APP_NAME,
            }
            if request.workflow_run_id:
                tags["workflow_run_id"] = request.workflow_run_id

            # Métadonnées libres de la requête (stringify)
            for k, v in request.metadata.items():
                tags[f"meta.{k}"] = str(v)[:250]  # limite MLflow sur les valeurs

            mlflow.set_tags(tags)

            run_id = run.info.run_id

        logger.info(
            "mlflow run logged",
            run_id=run_id,
            experiment=settings.MLFLOW_EXPERIMENT_NAME,
            provider=result.provider.value,
            model=result.model,
            latency_ms=result.latency_ms,
            total_tokens=result.token_usage.total_tokens,
        )
        return run_id

    # ── API publique asynchrone ───────────────────────────────────────────────

    async def log_inference(
        self,
        request: InferenceRequest,
        result: LLMResult,
        raw_prompt_template: str,
    ) -> str:
        """
        Log une inférence dans MLflow de façon non-bloquante.

        Returns:
            run_id : identifiant du run MLflow créé.
        """
        if not self._initialized:
            logger.warning("mlflow tracker not initialized, skipping log")
            return "untracked"

        try:
            run_id: str = await asyncio.to_thread(
                self._log_run_sync, request, result, raw_prompt_template
            )
            return run_id
        except Exception as exc:  # noqa: BLE001
            # Le tracking ne doit jamais faire échouer l'inférence
            logger.error(
                "mlflow logging failed",
                error=str(exc),
                agent_id=request.agent_id,
            )
            return "tracking-error"

    async def health_check(self) -> dict[str, Any]:
        """
        Vérifie la connectivité avec le serveur MLflow.
        Utilisé dans le /health endpoint de l'application.
        """
        try:
            # list_experiments est une opération légère
            def _check() -> str:
                client = mlflow.tracking.MlflowClient()
                experiments = client.search_experiments()
                return f"ok ({len(experiments)} experiments)"

            status = await asyncio.to_thread(_check)
            return {"status": "connected", "detail": status}
        except Exception as exc:  # noqa: BLE001
            return {"status": "unreachable", "detail": str(exc)}


# Singleton
mlflow_tracker = MLflowTracker()
