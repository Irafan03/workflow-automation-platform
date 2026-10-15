"""
orchestrator-service/app/graph/executor.py
Parcours du graphe de workflow et évaluation de chaque nœud.

Responsabilités :
  - Charger le graphe complet depuis PostgreSQL (Workflow + Nodes + AgentConfigs).
  - Parcourir les nœuds en suivant next_nodes (BFS itératif, ordre croissant).
  - Dispatcher chaque nœud vers le bon handler selon son node_type.
  - Propager le contexte (outputs précédents) entre les nœuds.
  - Appeler l'agent-llm-service pour les nœuds de type AGENT.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients.agent_llm import AgentInferenceRequest, agent_llm_client
from app.db.models import Node, NodeType, Workflow
from app.schemas.schemas import (
    AgentNodeConfig,
    ExecutionContext,
    NodeExecution,
    NodeExecutionStatus,
    WorkflowGraph,
    WorkflowNode,
)

logger = structlog.get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Chargement du graphe depuis PostgreSQL
# ══════════════════════════════════════════════════════════════════════════════

async def load_workflow_graph(
    workflow_id: str,
    session: AsyncSession,
) -> WorkflowGraph | None:
    """
    Charge un workflow actif et tous ses nœuds (avec AgentConfig) depuis la DB.

    Returns:
        WorkflowGraph si trouvé et actif, None sinon.
    """
    stmt = (
        select(Workflow)
        .where(Workflow.id == uuid.UUID(workflow_id))
        .options(
            selectinload(Workflow.nodes).selectinload(Node.agent_config)
        )
    )
    result = await session.execute(stmt)
    workflow = result.scalar_one_or_none()

    if workflow is None:
        logger.warning("workflow not found", workflow_id=workflow_id)
        return None

    if not workflow.is_active:
        logger.warning(
            "workflow is not active, skipping",
            workflow_id=workflow_id,
            status=workflow.status,
        )
        return None

    nodes = [_node_to_schema(n) for n in sorted(workflow.nodes, key=lambda n: n.order)]

    logger.info(
        "workflow graph loaded",
        workflow_id=workflow_id,
        node_count=len(nodes),
    )
    return WorkflowGraph(
        workflow_id=str(workflow.id),
        workflow_name=workflow.name,
        nodes=nodes,
    )


def _node_to_schema(node: Node) -> WorkflowNode:
    """Convertit un modèle SQLAlchemy Node en WorkflowNode Pydantic."""
    agent_cfg = None
    if node.agent_config:
        ac = node.agent_config
        agent_cfg = AgentNodeConfig(
            model_provider=ac.model_provider,
            model_name=ac.model_name,
            system_prompt=ac.system_prompt,
            temperature=ac.temperature,
            max_tokens=ac.max_tokens,
            tools=[str(t) for t in (ac.tools or [])],
        )
    return WorkflowNode(
        id=str(node.id),
        name=node.name,
        node_type=node.node_type.value if hasattr(node.node_type, "value") else str(node.node_type),
        config=node.config or {},
        next_nodes=[str(n) for n in (node.next_nodes or [])],
        order=node.order,
        agent_config=agent_cfg,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Exécution d'un nœud individuel
# ══════════════════════════════════════════════════════════════════════════════

async def execute_node(
    node: WorkflowNode,
    context: ExecutionContext,
) -> NodeExecution:
    """
    Exécute un nœud et retourne son journal d'exécution.
    Dispatche selon le node_type.
    """
    step = NodeExecution(
        node_id=node.id,
        node_name=node.name,
        node_type=node.node_type,
        status=NodeExecutionStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )

    t_start = time.perf_counter()
    try:
        output = await _dispatch_node(node, context)
        step.status = NodeExecutionStatus.SUCCESS
        step.output = output
    except Exception as exc:  # noqa: BLE001
        step.status = NodeExecutionStatus.FAILED
        step.error = str(exc)
        logger.error(
            "node execution failed",
            node_id=node.id,
            node_type=node.node_type,
            error=str(exc),
        )
    finally:
        step.finished_at = datetime.now(timezone.utc)
        step.duration_ms = (time.perf_counter() - t_start) * 1000

    return step


async def _dispatch_node(
    node: WorkflowNode,
    context: ExecutionContext,
) -> dict[str, Any]:
    """Route le nœud vers le handler approprié selon son type."""
    node_type = node.node_type.lower()

    if node_type == NodeType.AGENT.value:
        return await _handle_agent_node(node, context)
    elif node_type == NodeType.TRIGGER.value:
        return _handle_trigger_node(node, context)
    elif node_type == NodeType.ACTION.value:
        return await _handle_action_node(node, context)
    elif node_type == NodeType.CONDITION.value:
        return _handle_condition_node(node, context)
    elif node_type == NodeType.TRANSFORM.value:
        return _handle_transform_node(node, context)
    elif node_type == NodeType.OUTPUT.value:
        return _handle_output_node(node, context)
    else:
        logger.warning("unknown node type, treating as passthrough", node_type=node.node_type)
        return {"passed": True, "node_type": node.node_type}


# ── Handlers par type ─────────────────────────────────────────────────────────

async def _handle_agent_node(
    node: WorkflowNode,
    context: ExecutionContext,
) -> dict[str, Any]:
    """
    Nœud AGENT : appelle l'agent-llm-service avec le contexte courant.
    Injecte les outputs des nœuds précédents comme contexte du message.
    """
    cfg = node.agent_config
    if cfg is None:
        raise RuntimeError(f"Nœud AGENT '{node.name}' sans AgentConfig en base.")

    # Construction du message utilisateur : prompt du nœud + contexte des outputs précédents
    user_message = node.config.get("prompt", f"Exécute la tâche : {node.name}")
    if context.outputs:
        previous_outputs = "\n".join(
            f"[{nid}]: {str(out)[:500]}"
            for nid, out in context.outputs.items()
        )
        user_message = f"{user_message}\n\nContexte des étapes précédentes :\n{previous_outputs}"

    request = AgentInferenceRequest(
        agent_id=node.id,
        user_message=user_message,
        workflow_run_id=context.execution_log_id,
        system_prompt=cfg.system_prompt,
        model_provider=cfg.model_provider,
        model_name=cfg.model_name,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        tools=cfg.tools,
        metadata={
            "workflow_id": context.workflow_id,
            "workflow_name": context.workflow_name,
            "node_name": node.name,
        },
    )

    response = await agent_llm_client.infer(request)

    # Expose le mlflow_run_id dans le step pour remontée dans ExecutionLog
    output: dict[str, Any] = {
        "content": response.content,
        "provider": response.provider,
        "model": response.model,
        "latency_ms": response.latency_ms,
        "total_tokens": response.total_tokens,
        "mlflow_run_id": response.mlflow_run_id,
    }

    logger.info(
        "agent node executed",
        node_id=node.id,
        model=response.model,
        latency_ms=response.latency_ms,
        mlflow_run_id=response.mlflow_run_id,
    )
    return output


def _handle_trigger_node(
    node: WorkflowNode,
    context: ExecutionContext,
) -> dict[str, Any]:
    """Nœud TRIGGER : passthrough — retourne le payload de l'événement déclencheur."""
    return {
        "event_id": context.event.event_id,
        "source": context.event.source,
        "payload": context.event.payload,
    }


async def _handle_action_node(
    node: WorkflowNode,
    context: ExecutionContext,
) -> dict[str, Any]:
    """
    Nœud ACTION : exécution d'une action configurée (HTTP call, script, etc.).
    Pour l'instant, log et passthrough — à étendre selon les besoins.
    """
    action_type = node.config.get("action_type", "passthrough")
    logger.info("action node executed", node_id=node.id, action_type=action_type)
    return {
        "action_type": action_type,
        "config": node.config,
        "executed": True,
    }


def _handle_condition_node(
    node: WorkflowNode,
    context: ExecutionContext,
) -> dict[str, Any]:
    """
    Nœud CONDITION : évalue une condition simple sur les outputs précédents.
    Retourne branch: "true" | "false" pour guider next_nodes.
    """
    condition_key = node.config.get("condition_key", "")
    condition_value = node.config.get("condition_value")
    source_node_id = node.config.get("source_node_id", "")

    source_output = context.outputs.get(source_node_id, {})
    actual_value = source_output.get(condition_key)
    branch = "true" if actual_value == condition_value else "false"

    logger.info(
        "condition node evaluated",
        node_id=node.id,
        branch=branch,
        condition_key=condition_key,
    )
    return {"branch": branch, "evaluated": True}


def _handle_transform_node(
    node: WorkflowNode,
    context: ExecutionContext,
) -> dict[str, Any]:
    """
    Nœud TRANSFORM : applique une transformation simple sur les données.
    Pour l'instant, retourne une projection configurable.
    """
    source_node_id = node.config.get("source_node_id", "")
    fields = node.config.get("fields", [])
    source = context.outputs.get(source_node_id, {})
    result = {f: source.get(f) for f in fields} if fields else source
    return {"transformed": result}


def _handle_output_node(
    node: WorkflowNode,
    context: ExecutionContext,
) -> dict[str, Any]:
    """Nœud OUTPUT : collecte le résultat final du workflow."""
    source_node_id = node.config.get("source_node_id", "")
    final_output = context.outputs.get(source_node_id, context.outputs)
    return {"final_output": final_output, "workflow_id": context.workflow_id}


# ══════════════════════════════════════════════════════════════════════════════
# Parcours du graphe (BFS)
# ══════════════════════════════════════════════════════════════════════════════

async def execute_graph(
    graph: WorkflowGraph,
    context: ExecutionContext,
) -> ExecutionContext:
    """
    Parcourt le graphe en largeur (BFS) depuis les nœuds d'entrée.

    - Les nœuds sont exécutés dans l'ordre BFS.
    - La sortie de chaque nœud est ajoutée au contexte avant de passer au suivant.
    - Si un nœud échoue, on arrête le parcours et on remonte l'erreur.

    Returns:
        ExecutionContext mis à jour avec tous les steps.
    """
    visited: set[str] = set()
    queue: list[WorkflowNode] = list(graph.get_entry_nodes())

    if not queue:
        logger.warning("no entry nodes found in graph", workflow_id=graph.workflow_id)
        return context

    logger.info(
        "graph execution started",
        workflow_id=graph.workflow_id,
        entry_nodes=[n.id for n in queue],
    )

    while queue:
        node = queue.pop(0)

        if node.id in visited:
            continue
        visited.add(node.id)

        logger.info(
            "executing node",
            node_id=node.id,
            node_name=node.name,
            node_type=node.node_type,
        )

        step = await execute_node(node, context)

        # Récupère mlflow_run_id depuis l'output si nœud AGENT
        if node.node_type.lower() == NodeType.AGENT.value:
            step.mlflow_run_id = step.output.get("mlflow_run_id")

        context.add_step(step)

        # Arrête le parcours si le nœud a échoué
        if step.status == NodeExecutionStatus.FAILED:
            logger.error(
                "node failed, stopping graph execution",
                node_id=node.id,
                error=step.error,
            )
            raise RuntimeError(
                f"Nœud '{node.name}' ({node.node_type}) a échoué : {step.error}"
            )

        # Enqueue les nœuds suivants (en ordre croissant de position)
        for next_id in node.next_nodes:
            next_node = graph.get_node(next_id)
            if next_node and next_node.id not in visited:
                queue.append(next_node)

        # Tri pour respecter l'ordre déclaré
        queue.sort(key=lambda n: n.order)

    logger.info(
        "graph execution complete",
        workflow_id=graph.workflow_id,
        steps_count=len(context.steps),
        total_duration_ms=context.total_duration_ms(),
    )
    return context
