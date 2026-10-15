"""
orchestrator-service/app/db/models.py
Modèles SQLAlchemy 2.0 — miroir en lecture des tables gérées par l'api-gateway.

L'orchestrator-service ne crée PAS les tables (c'est le rôle de l'api-gateway
via Alembic). Il ne fait qu'y lire les workflows/nœuds et y écrire les logs
d'exécution. Les modèles sont donc déclarés identiques pour permettre les
requêtes ORM.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


# ── Enums (identiques à api-gateway) ─────────────────────────────────────────

class WorkflowStatus(str, PyEnum):
    DRAFT    = "draft"
    ACTIVE   = "active"
    PAUSED   = "paused"
    ARCHIVED = "archived"


class NodeType(str, PyEnum):
    TRIGGER   = "trigger"
    ACTION    = "action"
    CONDITION = "condition"
    AGENT     = "agent"
    TRANSFORM = "transform"
    OUTPUT    = "output"


class ExecutionStatus(str, PyEnum):
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCESS   = "success"
    FAILED    = "failed"
    CANCELLED = "cancelled"


# ── Modèles ───────────────────────────────────────────────────────────────────

class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflowstatus"), nullable=False, default=WorkflowStatus.DRAFT
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    nodes: Mapped[list["Node"]] = relationship(
        "Node", back_populates="workflow", lazy="selectin"
    )
    execution_logs: Mapped[list["ExecutionLog"]] = relationship(
        "ExecutionLog", back_populates="workflow"
    )


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[NodeType] = mapped_column(
        Enum(NodeType, name="nodetype"), nullable=False
    )
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Liste des UUID (str) des nœuds suivants dans le graphe
    next_nodes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="nodes")
    agent_config: Mapped["AgentConfig | None"] = relationship(
        "AgentConfig", back_populates="node", uselist=False, lazy="selectin"
    )


class AgentConfig(Base):
    __tablename__ = "agent_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)
    tools: Mapped[list | None] = mapped_column(JSON, nullable=True)
    mlflow_experiment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    node: Mapped["Node"] = relationship("Node", back_populates="agent_config")


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="executionstatus"),
        nullable=False,
        default=ExecutionStatus.PENDING,
    )
    trigger_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Détail pas-à-pas : liste de dicts {node_id, node_name, status, duration_ms, output}
    steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="execution_logs")
