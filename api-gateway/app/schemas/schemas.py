"""
api-gateway/app/schemas/schemas.py
Schémas Pydantic v2 pour la validation des payloads entrants/sortants.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import ExecutionStatus, NodeType, WorkflowStatus


# ── Helpers ───────────────────────────────────────────────────────────────────

class OrmBase(BaseModel):
    """Base commune : active le mode ORM (from_orm / model_validate)."""
    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════════════════════
# AgentConfig
# ═══════════════════════════════════════════════════════════════════════════════

class AgentConfigCreate(BaseModel):
    model_provider: str = Field(..., min_length=1, max_length=100)
    model_name: str = Field(..., min_length=1, max_length=100)
    model_version: str | None = Field(default=None, max_length=50)
    system_prompt: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=128_000)
    tools: list[dict[str, Any]] | None = None
    mlflow_experiment_id: str | None = None


class AgentConfigUpdate(BaseModel):
    model_provider: str | None = Field(default=None, max_length=100)
    model_name: str | None = Field(default=None, max_length=100)
    model_version: str | None = None
    system_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=128_000)
    tools: list[dict[str, Any]] | None = None
    mlflow_experiment_id: str | None = None


class AgentConfigResponse(OrmBase):
    id: uuid.UUID
    node_id: uuid.UUID
    model_provider: str
    model_name: str
    model_version: str | None
    system_prompt: str | None
    temperature: float
    max_tokens: int
    tools: list[dict[str, Any]] | None
    mlflow_experiment_id: str | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Node
# ═══════════════════════════════════════════════════════════════════════════════

class NodeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    node_type: NodeType
    position_x: float | None = None
    position_y: float | None = None
    config: dict[str, Any] | None = None
    next_nodes: list[str] | None = None
    order: int = Field(default=0, ge=0)
    agent_config: AgentConfigCreate | None = None  # fourni si node_type == AGENT


class NodeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    node_type: NodeType | None = None
    position_x: float | None = None
    position_y: float | None = None
    config: dict[str, Any] | None = None
    next_nodes: list[str] | None = None
    order: int | None = Field(default=None, ge=0)


class NodeResponse(OrmBase):
    id: uuid.UUID
    workflow_id: uuid.UUID
    name: str
    node_type: NodeType
    position_x: float | None
    position_y: float | None
    config: dict[str, Any] | None
    next_nodes: list[str] | None
    order: int
    agent_config: AgentConfigResponse | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow
# ═══════════════════════════════════════════════════════════════════════════════

class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: WorkflowStatus = WorkflowStatus.DRAFT
    is_active: bool = False
    meta: dict[str, Any] | None = None
    nodes: list[NodeCreate] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: WorkflowStatus | None = None
    is_active: bool | None = None
    meta: dict[str, Any] | None = None


class WorkflowSummary(OrmBase):
    """Version allégée sans les nœuds, pour les listes paginées."""
    id: uuid.UUID
    name: str
    description: str | None
    status: WorkflowStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WorkflowResponse(OrmBase):
    """Version complète avec nœuds imbriqués."""
    id: uuid.UUID
    name: str
    description: str | None
    status: WorkflowStatus
    is_active: bool
    meta: dict[str, Any] | None
    nodes: list[NodeResponse]
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# ExecutionLog
# ═══════════════════════════════════════════════════════════════════════════════

class ExecutionLogResponse(OrmBase):
    id: uuid.UUID
    workflow_id: uuid.UUID
    status: ExecutionStatus
    trigger_payload: dict[str, Any] | None
    output: dict[str, Any] | None
    error_message: str | None
    steps: list[dict[str, Any]] | None
    duration_ms: int | None
    mlflow_run_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Réponses génériques paginées
# ═══════════════════════════════════════════════════════════════════════════════

class PaginatedWorkflows(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[WorkflowSummary]
