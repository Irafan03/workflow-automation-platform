"""
trigger-service/app/adapters/base.py
Classe abstraite BaseAdapter — contrat que tous les adaptateurs doivent respecter.
"""
from abc import ABC, abstractmethod
from typing import Any

from fastapi import Request

from app.schemas.events import NormalizedEvent


class BaseAdapter(ABC):
    """
    Interface commune à tous les adaptateurs de déclencheurs.

    Chaque adaptateur est responsable de :
    1. Valider/parser le payload brut entrant (validate).
    2. Normaliser le payload en NormalizedEvent canonique (normalize).
    3. Vérifier l'authenticité de la requête si applicable (verify_signature).

    Les adaptateurs ne publient PAS dans Redis directement :
    c'est la route FastAPI qui orchestre valider → normaliser → publier.
    """

    # Identifiant lisible de la source (ex: "webhook", "telegram", "gmail")
    source_name: str = "unknown"

    @abstractmethod
    async def validate(self, request: Request) -> Any:
        """
        Parse et valide le payload brut de la requête HTTP.

        Args:
            request: Requête FastAPI brute.

        Returns:
            L'objet Pydantic correspondant au payload source validé.

        Raises:
            fastapi.HTTPException: Si le payload est invalide.
        """
        ...

    @abstractmethod
    async def normalize(self, raw: Any, meta: dict[str, Any] | None = None) -> NormalizedEvent:
        """
        Transforme le payload validé en NormalizedEvent canonique.

        Args:
            raw:  Objet retourné par validate().
            meta: Métadonnées techniques (headers, IP…).

        Returns:
            NormalizedEvent prêt à être publié dans Redis.
        """
        ...

    async def verify_signature(self, request: Request) -> bool:
        """
        Vérifie l'authenticité de la requête (HMAC, token bearer, etc.).
        Par défaut retourne True (pas de vérification).
        Surcharger dans les adaptateurs qui l'implémentent.

        Returns:
            True si la signature est valide, False sinon.
        """
        return True

    async def process(self, request: Request) -> NormalizedEvent:
        """
        Pipeline complet : verify → validate → normalize.
        Point d'entrée appelé par les routes FastAPI.

        Raises:
            fastapi.HTTPException 401: Si la signature est invalide.
            fastapi.HTTPException 422: Si le payload est invalide.
        """
        from fastapi import HTTPException, status

        # 1. Vérification de la signature
        if not await self.verify_signature(request):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Signature invalide pour l'adaptateur {self.source_name}.",
            )

        # 2. Extraction des métadonnées HTTP
        meta: dict[str, Any] = {
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "content_type": request.headers.get("content-type"),
        }

        # 3. Validation + normalisation
        raw = await self.validate(request)
        return await self.normalize(raw, meta)
