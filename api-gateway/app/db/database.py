"""
api-gateway/app/db/database.py
Configuration de la session SQLAlchemy async + dépendance FastAPI.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# ── Moteur async ──────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,          # vérifie la connexion avant chaque utilisation
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,      # évite les lazy-loads après commit
    autoflush=False,
)


# ── Classe de base pour tous les modèles ─────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dépendance FastAPI ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Injecte une session DB dans les routes FastAPI."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
