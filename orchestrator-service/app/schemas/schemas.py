"""
orchestrator-service/app/schemas/schemas.py
Schémas Pydantic internes à l'orchestrateur.

Ces schémas représentent :
  - L'événement consommé depuis Redis (NormalizedEvent)
  - La structure du graphe de workflow chargé depuis PostgreSQL
  - L'état d'exécution pas-à-pas (NodeExecution, ExecutionContext)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════════════════
# Événement Redis (format publié par le trigger-service)
# ══════════════════════════════════════════════════════════════════════════════

class NormalizedEvent(BaseModel):
    """
    Événement canonique désérialisé depuis la file Redis.
    Doit correspondre au format émis par le trigger-service.
    """
    event_id: str
    source: str
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)

    def get_workflow_id(self) -> str | None:
        """
        Tente de retrouver le workflow_id dans payload puis meta.
        Le trigger peut l'injecter dans l'un ou l'autre champ.
        """
        return (
            self.payload.get("workflow_id")
            or self.meta.get("workflow_id")
        )


# ══════════════════════════════════════════════════════════════════════════════
# Graphe de workflow (structure chargée depuis PostgreSQL)
# ══════════════════════════════════════════════════════════════════════════════

class AgentNodeConfig(BaseModel):
    """Configuration IA d'un nœud de type AGENT."""
    model_provider: str
    model_name: str
    system_prompt: str | None = None
    temperature: float = 0.7
    max_tokens: int = 1024
    tools: list[str] = Field(default_factory=list)


class WorkflowNode(BaseModel):
    """Représentation d'un nœud du graphe, prête pour l'exécution."""
    id: str                        # UUID sous forme de str pour faciliter les comparaisons
    name: str
    node_type: str                 # trigger / action / condition / agent / transform / output
    config: dict[str, Any] = Field(default_factory=dict)
    next_nodes: list[str] = Field(default_factory=list)   # IDs des nœuds suivants
    order: int = 0
    agent_config: AgentNodeConfig | None = None


class WorkflowGraph(BaseModel):
    """
    Graphe complet d'un workflow — chargé une fois depuis PostgreSQL
    au début de chaque exécution.
    """
    workflow_id: str
    workflow_name: str
    nodes: list[WorkflowNode] = Field(default_factory=list)

    def get_node(self, node_id: str) -> WorkflowNode | None:
        """Retourne un nœud par son ID."""
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def get_entry_nodes(self) -> list[WorkflowNode]:
        """
        Retourne les nœuds d'entrée du graphe.
        Priorité : nœuds de type TRIGGER, sinon nœud avec le plus petit order.
        """
        trigger_nodes = [n for n in self.nodes if n.node_type == "trigger"]
        if trigger_nodes:
            return sorted(trigger_nodes, key=lambda n: n.order)
        if self.nodes:
            return [min(self.nodes, key=lambda n: n.order)]
        return []


# ══════════════════════════════════════════════════════════════════════════════
# État d'exécution d'un nœud
# ══════════════════════════════════════════════════════════════════════════════

class NodeExecutionStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    SUCCESS  = "success"
    FAILED   = "failed"
    SKIPPED  = "skipped"


class NodeExecution(BaseModel):
    """Journal d'exécution d'un nœud individuel."""
    node_id: str
    node_name: str
    node_type: str
    status: NodeExecutionStatus = NodeExecutionStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float = 0.0
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    # Rempli uniquement pour les nœuds AGENT
    mlflow_run_id: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# Contexte d'exécution global (partagé entre tous les composants du pipeline)
# ══════════════════════════════════════════════════════════════════════════════

class ExecutionContext(BaseModel):
    """
    État global d'une exécution de workflow.
    Passé de nœud en nœud pour propager les sorties précédentes.
    """
    execution_log_id: str
    workflow_id: str
    workflow_name: str
    event: NormalizedEvent
    steps: list[NodeExecution] = Field(default_factory=list)
    # Sortie cumulée : clé = node_id, valeur = output du nœud
    outputs: dict[str, Any] = Field(default_factory=dict)
    # Premier mlflow_run_id rencontré (pour l'ExecutionLog principal)
    mlflow_run_id: str | None = None

    def add_step(self, step: NodeExecution) -> None:
        self.steps.append(step)
        if step.output:
            self.outputs[step.node_id] = step.output
        if step.mlflow_run_id and not self.mlflow_run_id:
            self.mlflow_run_id = step.mlflow_run_id

    def steps_as_dicts(self) -> list[dict[str, Any]]:
        """Sérialise les étapes pour stockage JSON dans ExecutionLog.steps."""
        return [s.model_dump(mode="json") for s in self.steps]

    def total_duration_ms(self) -> int:
        return int(sum(s.duration_ms for s in self.steps))
