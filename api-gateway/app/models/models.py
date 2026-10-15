"""
api-gateway/app/models/models.py
Modèles SQLAlchemy 2.0 — Workflow, Node, AgentConfig, ExecutionLog.
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


# ── Enums ─────────────────────────────────────────────────────────────────────

class WorkflowStatus(str, PyEnum):
    DRAFT    = "draft"
    ACTIVE   = "active"
    PAUSED   = "paused"
    ARCHIVED = "archived"


class NodeType(str, PyEnum):
    TRIGGER    = "trigger"
    ACTION     = "action"
    CONDITION  = "condition"
    AGENT      = "agent"
    TRANSFORM  = "transform"
    OUTPUT     = "output"


class ExecutionStatus(str, PyEnum):
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCESS   = "success"
    FAILED    = "failed"
    CANCELLED = "cancelled"


# ── Modèles ───────────────────────────────────────────────────────────────────

class Workflow(Base):
    """
    Représente un workflow d'automatisation complet.
    Un workflow est un graphe orienté de Nodes.
    """
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus), nullable=False, default=WorkflowStatus.DRAFT
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Métadonnées libres (tags, version, etc.)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relations
    nodes: Mapped[list["Node"]] = relationship(
        "Node", back_populates="workflow", cascade="all, delete-orphan"
    )
    execution_logs: Mapped[list["ExecutionLog"]] = relationship(
        "ExecutionLog", back_populates="workflow", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Workflow id={self.id} name={self.name!r} status={self.status}>"


class Node(Base):
    """
    Nœud individuel d'un workflow (trigger, action, agent, condition…).
    Stocke sa configuration comme JSON pour rester générique.
    """
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
        Enum(NodeType), nullable=False
    )

    # Position dans l'éditeur visuel
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Configuration spécifique au type de nœud (paramètres, credentials…)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Connexions sortantes : liste d'IDs de nœuds cibles
    next_nodes: Mapped[list | None] = mapped_column(JSON, nullable=True)

    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relations
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="nodes")
    agent_config: Mapped["AgentConfig | None"] = relationship(
        "AgentConfig", back_populates="node", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Node id={self.id} type={self.node_type} name={self.name!r}>"


class AgentConfig(Base):
    """
    Configuration étendue pour les nœuds de type AGENT.
    Stocke les paramètres du modèle IA, le prompt système, etc.
    """
    __tablename__ = "agent_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # 1-1 avec Node
        index=True,
    )

    # Modèle IA
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False)  # openai, anthropic…
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)       # gpt-4o, claude-3…
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Prompt
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)

    # Outils / fonctions disponibles pour l'agent
    tools: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Suivi MLflow
    mlflow_experiment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relation
    node: Mapped["Node"] = relationship("Node", back_populates="agent_config")

    def __repr__(self) -> str:
        return f"<AgentConfig id={self.id} model={self.model_provider}/{self.model_name}>"


class ExecutionLog(Base):
    """
    Journal d'exécution d'un workflow.
    Chaque déclenchement crée une entrée ; les nœuds exécutés
    sont loggés dans le champ JSONB `steps`.
    """
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
        Enum(ExecutionStatus), nullable=False, default=ExecutionStatus.PENDING
    )

    # Données d'entrée du déclenchement
    trigger_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Résultat final
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Détail des étapes (liste de dicts : node_id, status, duration_ms, output)
    steps: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Durée totale en millisecondes
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ID de run MLflow associé (traçabilité des agents IA)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relation
    workflow: Mapped["Workflow"] = relationship(
        "Workflow", back_populates="execution_logs"
    )

    def __repr__(self) -> str:
        return f"<ExecutionLog id={self.id} workflow={self.workflow_id} status={self.status}>"
