"""
api-gateway/alembic/env.py
Configuration Alembic — supporte les migrations async (asyncpg).
"""
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Charge les modèles pour que Alembic détecte les changements de schéma
from app.db.database import Base  # noqa: F401 — importe Base
import app.models.models  # noqa: F401 — enregistre tous les modèles dans Base.metadata

config = context.config

# Configure le logging depuis alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """
    Lit DATABASE_URL depuis l'environnement et adapte le driver pour Alembic.
    Alembic a besoin du driver sync (psycopg2), pas asyncpg.
    """
    url = os.getenv(
        "DATABASE_URL",
        "postgresql://workflow_user:changeme@localhost:5432/workflow_db",
    )
    # Remplace le driver async par le driver sync si nécessaire
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def run_migrations_offline() -> None:
    """Mode offline : génère le SQL sans connexion à la DB."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Mode online : connexion async via asyncpg, migration via psycopg2."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
