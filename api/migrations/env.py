"""Entorno de Alembic. Siempre conecta con el usuario de MIGRACIONES (ADR 0019).

La URL y el rol de ejecución llegan por `config.attributes` (desde `python -m app
migrate` o los tests) o, en su defecto, de las variables de entorno.
"""

from alembic import context
from sqlalchemy import create_engine

from app.config import Settings
from app.db import normalize_url

config = context.config


def _url() -> str:
    url = config.attributes.get("url") or Settings().migration_database_url
    if not url:
        raise RuntimeError("Falta MIGRATION_DATABASE_URL (usuario de migraciones).")
    return normalize_url(url)


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is not None:
        _run(connectable)
        return
    engine = create_engine(_url())
    with engine.connect() as connection:
        _run(connection)
    engine.dispose()


def _run(connection) -> None:  # noqa: ANN001
    context.configure(connection=connection, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Solo se admiten migraciones en línea.")
run_migrations_online()
