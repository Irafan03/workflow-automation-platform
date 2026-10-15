"""
agent-llm-service/app/prompts/manager.py
Gestionnaire de prompts dynamiques.

Responsabilités :
- Stocker les templates de system prompts nommés.
- Injecter les variables dans les templates (Jinja2-lite via str.format_map).
- Construire le prompt final en tenant compte de la surcharge par requête.
- Exposer le template brut pour le logging MLflow (avant injection des variables).
"""
from __future__ import annotations

from typing import Any

import structlog

from app.schemas.schemas import PromptOverride, ToolName

logger = structlog.get_logger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Registre de templates
# ══════════════════════════════════════════════════════════════════════════════

# Clé → template de system prompt.
# Les variables sont entre accolades simples : {variable_name}
_PROMPT_REGISTRY: dict[str, str] = {
    "default": (
        "Tu es un assistant IA expert en automatisation de workflows. "
        "Tu dois répondre de manière concise, factuelle et en {language}. "
        "Workflow en cours : {workflow_name}."
    ),
    "summarizer": (
        "Tu es un agent spécialisé dans la synthèse de contenu. "
        "Résume le contenu fourni en {max_sentences} phrases maximum, "
        "en {language}. Sois précis et neutre."
    ),
    "email_analyzer": (
        "Tu es un agent d'analyse d'emails. "
        "Pour chaque email fourni, extrait : l'expéditeur, le sujet, "
        "le niveau d'urgence (low/medium/high) et une action suggérée. "
        "Réponds en JSON valide uniquement."
    ),
    "code_reviewer": (
        "Tu es un expert en révision de code. "
        "Analyse le code fourni et identifie : les bugs potentiels, "
        "les problèmes de sécurité, et les améliorations de performance. "
        "Réponds en {language} avec des exemples concrets."
    ),
    "orchestrator": (
        "Tu es le cerveau central d'une plateforme d'automatisation. "
        "Tu reçois un contexte d'exécution et tu dois décider quelles actions "
        "effectuer parmi les outils disponibles : {available_tools}. "
        "Réponds en JSON avec les clés 'action', 'tool', 'parameters'."
    ),
}

# Variables par défaut utilisées si non fournies dans template_variables
_DEFAULT_VARIABLES: dict[str, str] = {
    "language": "français",
    "workflow_name": "workflow par défaut",
    "max_sentences": "5",
    "available_tools": "web_search, code_interpreter, file_reader, http_request",
}


# ══════════════════════════════════════════════════════════════════════════════
# Suffixes outils
# ══════════════════════════════════════════════════════════════════════════════

_TOOL_SUFFIXES: dict[ToolName, str] = {
    ToolName.WEB_SEARCH: (
        "\n\nTu as accès à l'outil web_search pour rechercher des informations récentes."
    ),
    ToolName.CODE_INTERPRETER: (
        "\n\nTu peux exécuter du code Python via l'outil code_interpreter."
    ),
    ToolName.FILE_READER: (
        "\n\nTu peux lire des fichiers locaux via l'outil file_reader."
    ),
    ToolName.HTTP_REQUEST: (
        "\n\nTu peux effectuer des requêtes HTTP externes via l'outil http_request."
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# PromptManager
# ══════════════════════════════════════════════════════════════════════════════

class PromptManager:
    """
    Construit le system prompt final à partir d'un template ou d'une surcharge
    directe, puis injecte les suffixes des outils activés.
    """

    def get_template(self, template_id: str) -> str:
        """Retourne le template brut (non interpolé) depuis le registre."""
        if template_id not in _PROMPT_REGISTRY:
            logger.warning(
                "prompt template not found, falling back to default",
                template_id=template_id,
            )
            return _PROMPT_REGISTRY["default"]
        return _PROMPT_REGISTRY[template_id]

    def resolve(
        self,
        prompt_override: PromptOverride | None,
        tools: list[ToolName],
    ) -> tuple[str, str]:
        """
        Construit le system prompt final.

        Returns:
            (system_prompt, raw_template)
            - system_prompt  : prompt prêt à envoyer au LLM
            - raw_template   : template brut avant injection (pour MLflow)
        """
        # 1. Déterminer le template brut et les variables
        if prompt_override and prompt_override.system_prompt:
            # Surcharge directe : le texte fourni EST le prompt final
            raw_template = prompt_override.system_prompt
            system_prompt = raw_template
            logger.debug("using direct system_prompt override")

        elif prompt_override and prompt_override.prompt_template_id:
            raw_template = self.get_template(prompt_override.prompt_template_id)
            variables = _DEFAULT_VARIABLES | prompt_override.template_variables
            system_prompt = self._interpolate(raw_template, variables)
            logger.debug(
                "using named template",
                template_id=prompt_override.prompt_template_id,
            )

        else:
            # Aucune surcharge → template par défaut
            raw_template = _PROMPT_REGISTRY["default"]
            system_prompt = self._interpolate(raw_template, _DEFAULT_VARIABLES)
            logger.debug("using default prompt template")

        # 2. Ajouter les suffixes des outils activés
        for tool in tools:
            suffix = _TOOL_SUFFIXES.get(tool, "")
            system_prompt += suffix

        return system_prompt, raw_template

    @staticmethod
    def _interpolate(template: str, variables: dict[str, Any]) -> str:
        """
        Injecte les variables dans le template.
        Les clés manquantes sont laissées telles quelles (pas d'exception).
        """
        try:
            return template.format_map(_SafeDict(variables))
        except Exception as exc:  # noqa: BLE001
            logger.warning("prompt interpolation failed", error=str(exc))
            return template

    def list_templates(self) -> list[str]:
        """Retourne les identifiants de templates disponibles."""
        return list(_PROMPT_REGISTRY.keys())

    def register(self, template_id: str, template: str) -> None:
        """Enregistre un nouveau template (utile pour les tests)."""
        _PROMPT_REGISTRY[template_id] = template
        logger.info("prompt template registered", template_id=template_id)


class _SafeDict(dict):
    """dict qui retourne '{key}' pour les clés manquantes (pas de KeyError)."""

    def __missing__(self, key: str) -> str:  # type: ignore[override]
        return f"{{{key}}}"


# Singleton
prompt_manager = PromptManager()
