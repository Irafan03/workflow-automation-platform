"""
agent-llm-service/app/schemas/schemas.py
Schémas Pydantic pour les requêtes et réponses d'inférence LLM.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════════════════
# Enums
# ══════════════════════════════════════════════════════════════════════════════

class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"


class ToolName(str, Enum):
    """Outils activables par l'agent lors d'une inférence."""
    WEB_SEARCH = "web_search"
    CODE_INTERPRETER = "code_interpreter"
    FILE_READER = "file_reader"
    HTTP_REQUEST = "http_request"


# ══════════════════════════════════════════════════════════════════════════════
# Requête
# ══════════════════════════════════════════════════════════════════════════════

class PromptOverride(BaseModel):
    """Surcharge optionnelle du prompt système pour une requête spécifique."""
    system_prompt: str | None = Field(
        default=None,
        description="Remplace intégralement le system prompt par défaut.",
        max_length=8192,
    )
    prompt_template_id: str | None = Field(
        default=None,
        description=(
            "Identifiant d'un template de prompt préenregistré. "
            "Ignoré si system_prompt est fourni."
        ),
    )
    template_variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Variables injectées dans le template de prompt.",
    )


class InferenceRequest(BaseModel):
    """Corps de la requête POST /api/v1/inference."""

    # Contexte de l'agent
    agent_id: str = Field(
        ...,
        description="Identifiant de l'agent qui déclenche l'inférence.",
        examples=["agent-abc123"],
    )
    workflow_run_id: str | None = Field(
        default=None,
        description="ID du run de workflow associé (pour corrélation).",
    )

    # Message utilisateur
    user_message: str = Field(
        ...,
        description="Message ou instruction envoyé au modèle.",
        min_length=1,
        max_length=32768,
        examples=["Résume les emails non lus de cette semaine."],
    )

    # Historique de conversation (multi-turn)
    conversation_history: list[dict[str, str]] = Field(
        default_factory=list,
        description=(
            "Historique des échanges précédents. "
            "Chaque entrée doit avoir les clés 'role' ('user'|'assistant') et 'content'."
        ),
        examples=[[{"role": "user", "content": "Bonjour"}, {"role": "assistant", "content": "Bonjour ! Comment puis-je aider ?"}]],
    )

    # Surcharge du prompt
    prompt_override: PromptOverride | None = Field(
        default=None,
        description="Surcharge optionnelle du system prompt.",
    )

    # Paramètres LLM (surcharge les valeurs par défaut de la config)
    provider: LLMProvider | None = Field(
        default=None,
        description="Provider LLM à utiliser. Utilise LLM_PROVIDER de la config si absent.",
    )
    model: str | None = Field(
        default=None,
        description="Modèle à utiliser. Utilise le modèle par défaut du provider si absent.",
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Température de sampling (0 = déterministe, 2 = très créatif).",
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        le=8192,
        description="Nombre maximum de tokens dans la réponse.",
    )

    # Outils activés
    tools: list[ToolName] = Field(
        default_factory=list,
        description="Liste des outils activés pour cette inférence.",
    )

    # Métadonnées libres
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Métadonnées arbitraires loguées dans MLflow.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Réponse
# ══════════════════════════════════════════════════════════════════════════════

class TokenUsage(BaseModel):
    """Consommation de tokens retournée par le LLM."""
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class InferenceResponse(BaseModel):
    """Corps de la réponse de POST /api/v1/inference."""

    # Identification
    agent_id: str = Field(..., description="Identifiant de l'agent.")
    workflow_run_id: str | None = Field(default=None)

    # Réponse du modèle
    content: str = Field(..., description="Texte généré par le modèle.")

    # Méta LLM
    provider: LLMProvider = Field(..., description="Provider LLM effectivement utilisé.")
    model: str = Field(..., description="Modèle effectivement utilisé.")
    temperature: float = Field(..., description="Température utilisée.")

    # Tokens
    token_usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Détail de la consommation de tokens.",
    )

    # Performance
    latency_ms: float = Field(..., description="Temps de réponse du LLM en millisecondes.")

    # MLflow
    mlflow_run_id: str = Field(
        ...,
        description="ID du run MLflow associé à cette inférence.",
    )
    mlflow_experiment_name: str = Field(
        ...,
        description="Nom de l'expérience MLflow.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Réponse d'erreur enrichie
# ══════════════════════════════════════════════════════════════════════════════

class ErrorDetail(BaseModel):
    """Corps standard des réponses d'erreur."""
    detail: str
    error_type: str | None = None
    agent_id: str | None = None
    workflow_run_id: str | None = None
