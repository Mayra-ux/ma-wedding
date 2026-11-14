"""Ejecuta las migraciones de Alembic con el usuario de migraciones."""

from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def alembic_config(url: str | None = None, runtime_role: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    if url:
        cfg.attributes["url"] = url
    if runtime_role:
        cfg.attributes["runtime_role"] = runtime_role
    return cfg


def upgrade(url: str | None = None, runtime_role: str | None = None) -> None:
    command.upgrade(alembic_config(url, runtime_role), "head")


def downgrade_base(url: str | None = None, runtime_role: str | None = None) -> None:
    command.downgrade(alembic_config(url, runtime_role), "base")
