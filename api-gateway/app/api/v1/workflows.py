"""
api-gateway/app/api/v1/workflows.py
Routes CRUD pour les Workflows — FastAPI Router.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.models import AgentConfig, Node, Workflow
from app.schemas.schemas import (
    PaginatedWorkflows,
    WorkflowCreate,
    WorkflowResponse,
    WorkflowSummary,
    WorkflowUpdate,
)

router = APIRouter(prefix="/workflows", tags=["Workflows"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_workflow_or_404(db: AsyncSession, workflow_id: uuid.UUID) -> Workflow:
    """Charge un workflow avec ses nœuds et configs d'agents, ou lève 404."""
    result = await db.execute(
        select(Workflow)
        .where(Workflow.id == workflow_id)
        .options(
            selectinload(Workflow.nodes).selectinload(Node.agent_config)
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} introuvable.",
        )
    return workflow


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un workflow",
)
async def create_workflow(payload: WorkflowCreate, db: DbDep) -> WorkflowResponse:
    """
    Crée un nouveau workflow avec ses nœuds.
    Si un nœud est de type AGENT, sa configuration étendue est persistée.
    """
    workflow = Workflow(
        name=payload.name,
        description=payload.description,
        status=payload.status,
        is_active=payload.is_active,
        meta=payload.meta,
    )
    db.add(workflow)
    await db.flush()  # obtient l'ID avant d'insérer les nœuds

    for idx, node_data in enumerate(payload.nodes):
        node = Node(
            workflow_id=workflow.id,
            name=node_data.name,
            node_type=node_data.node_type,
            position_x=node_data.position_x,
            position_y=node_data.position_y,
            config=node_data.config,
            next_nodes=node_data.next_nodes,
            order=node_data.order if node_data.order is not None else idx,
        )
        db.add(node)
        await db.flush()

        # Persist AgentConfig si fournie
        if node_data.agent_config:
            agent_cfg = AgentConfig(
                node_id=node.id,
                **node_data.agent_config.model_dump(),
            )
            db.add(agent_cfg)

    await db.commit()
    return await _get_workflow_or_404(db, workflow.id)


@router.get(
    "/",
    response_model=PaginatedWorkflows,
    summary="Lister les workflows (paginé)",
)
async def list_workflows(
    db: DbDep,
    page: int = Query(default=1, ge=1, description="Numéro de page"),
    page_size: int = Query(default=20, ge=1, le=100, description="Éléments par page"),
    status_filter: str | None = Query(default=None, alias="status"),
) -> PaginatedWorkflows:
    """Retourne la liste paginée des workflows (sans les nœuds pour alléger)."""
    base_query = select(Workflow)

    if status_filter:
        base_query = base_query.where(Workflow.status == status_filter)

    # Compte total
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    # Page courante
    offset = (page - 1) * page_size
    result = await db.execute(
        base_query.order_by(Workflow.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    workflows = result.scalars().all()

    return PaginatedWorkflows(
        total=total,
        page=page,
        page_size=page_size,
        items=[WorkflowSummary.model_validate(w) for w in workflows],
    )


@router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    summary="Récupérer un workflow par ID",
)
async def get_workflow(workflow_id: uuid.UUID, db: DbDep) -> WorkflowResponse:
    """Retourne le workflow complet avec tous ses nœuds et configurations d'agents."""
    workflow = await _get_workflow_or_404(db, workflow_id)
    return WorkflowResponse.model_validate(workflow)


@router.patch(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    summary="Mettre à jour un workflow",
)
async def update_workflow(
    workflow_id: uuid.UUID, payload: WorkflowUpdate, db: DbDep
) -> WorkflowResponse:
    """Met à jour les champs fournis (PATCH partiel)."""
    workflow = await _get_workflow_or_404(db, workflow_id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(workflow, field, value)

    await db.commit()
    return await _get_workflow_or_404(db, workflow_id)


@router.delete(
    "/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un workflow",
)
async def delete_workflow(workflow_id: uuid.UUID, db: DbDep) -> None:
    """Supprime un workflow et en cascade tous ses nœuds et logs d'exécution."""
    workflow = await _get_workflow_or_404(db, workflow_id)
    await db.delete(workflow)
    await db.commit()
