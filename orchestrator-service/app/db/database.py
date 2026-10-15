"""
orchestrator-service/app/db/database.py
Configuration du moteur SQLAlchemy async + session factory.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── Moteur async ──────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,       # vérifie la connexion avant utilisation
    pool_recycle=1800,        # recycle les connexions après 30 min
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # évite les lazy-loads post-commit
    autoflush=False,
)


# ── Classe de base partagée par tous les modèles ──────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Context manager de session (utilisé dans le worker) ──────────────────────
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Fournit une session DB dans un context manager async."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
