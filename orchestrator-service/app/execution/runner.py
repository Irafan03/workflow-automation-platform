"""
orchestrator-service/app/execution/runner.py
Pipeline d'exécution complet d'un workflow.

Pour chaque événement reçu depuis Redis :
  1. Résoudre le workflow_id depuis l'événement.
  2. Charger le graphe depuis PostgreSQL.
  3. Créer un ExecutionLog en statut RUNNING avec horodatage de début.
  4. Parcourir le graphe via GraphExecutor.
  5. Mettre à jour l'ExecutionLog en SUCCESS ou FAILED avec horodatage de fin.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.db.models import ExecutionLog, ExecutionStatus
from app.graph.executor import execute_graph, load_workflow_graph
from app.schemas.schemas import ExecutionContext, NormalizedEvent

logger = structlog.get_logger(__name__)


class WorkflowRunner:
    """
    Orchestre l'exécution complète d'un workflow déclenché par un événement Redis.
    Utilisé comme handler par le RedisConsumer.
    """

    async def handle_event(self, event: NormalizedEvent) -> None:
        """
        Point d'entrée appelé par le consumer pour chaque événement.

        Résout le workflow_id, charge le graphe, exécute et log le résultat.
        """
        log = logger.bind(event_id=event.event_id, source=event.source)

        workflow_id = event.get_workflow_id()
        if not workflow_id:
            log.warning(
                "event has no workflow_id, dropping",
                payload_keys=list(event.payload.keys()),
            )
            return

        log = log.bind(workflow_id=workflow_id)
        log.info("handling workflow event")

        async with AsyncSessionLocal() as session:
            await self._run(session, event, workflow_id, log)

    async def _run(
        self,
        session: AsyncSession,
        event: NormalizedEvent,
        workflow_id: str,
        log: Any,
    ) -> None:
        """Pipeline complet dans une session DB partagée."""

        # ── 1. Charger le graphe ──────────────────────────────────────────────
        graph = await load_workflow_graph(workflow_id, session)
        if graph is None:
            log.warning("workflow not found or inactive, skipping")
            return

        # ── 2. Créer l'ExecutionLog en statut RUNNING ─────────────────────────
        execution_log = ExecutionLog(
            id=uuid.uuid4(),
            workflow_id=uuid.UUID(workflow_id),
            status=ExecutionStatus.RUNNING,
            trigger_payload={
                "event_id": event.event_id,
                "source": event.source,
                "timestamp": event.timestamp,
                "payload": event.payload,
                "meta": event.meta,
            },
            started_at=datetime.now(timezone.utc),
        )
        session.add(execution_log)
        await session.flush()   # obtenir l'ID sans commit complet

        log = log.bind(execution_log_id=str(execution_log.id))
        log.info("execution log created", status="RUNNING")

        # ── 3. Construire le contexte d'exécution ─────────────────────────────
        context = ExecutionContext(
            execution_log_id=str(execution_log.id),
            workflow_id=workflow_id,
            workflow_name=graph.workflow_name,
            event=event,
        )

        # ── 4. Parcourir le graphe ────────────────────────────────────────────
        error_message: str | None = None
        try:
            context = await execute_graph(graph, context)
            final_status = ExecutionStatus.SUCCESS
            log.info(
                "workflow execution succeeded",
                steps=len(context.steps),
                duration_ms=context.total_duration_ms(),
            )
        except Exception as exc:  # noqa: BLE001
            final_status = ExecutionStatus.FAILED
            error_message = str(exc)
            log.error("workflow execution failed", error=error_message)

        # ── 5. Mettre à jour l'ExecutionLog ───────────────────────────────────
        finished_at = datetime.now(timezone.utc)
        duration_ms = int(
            (finished_at - execution_log.started_at).total_seconds() * 1000
        )

        # Collecte du dernier output (nœud OUTPUT ou dernier step réussi)
        final_output = _extract_final_output(context)

        execution_log.status = final_status
        execution_log.finished_at = finished_at
        execution_log.duration_ms = duration_ms
        execution_log.steps = context.steps_as_dicts()
        execution_log.output = final_output
        execution_log.error_message = error_message
        execution_log.mlflow_run_id = context.mlflow_run_id

        await session.commit()

        log.info(
            "execution log updated",
            status=final_status.value,
            duration_ms=duration_ms,
            mlflow_run_id=context.mlflow_run_id,
        )


def _extract_final_output(context: ExecutionContext) -> dict[str, Any]:
    """
    Extrait la sortie finale du contexte :
    - Priorité au nœud de type OUTPUT s'il existe.
    - Sinon le dernier step réussi.
    - Sinon dict vide.
    """
    # Cherche un step de type OUTPUT
    for step in reversed(context.steps):
        if step.node_type.lower() == "output" and step.status.value == "success":
            return step.output

    # Dernier step réussi
    for step in reversed(context.steps):
        if step.status.value == "success" and step.output:
            return step.output

    return {}


# Singleton
workflow_runner = WorkflowRunner()
