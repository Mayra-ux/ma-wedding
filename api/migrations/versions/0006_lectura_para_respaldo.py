"""Lectura para el respaldo con el usuario de ejecución (I-10; doc 10).

`pg_dump` bloquea y lee todas las tablas y el estado de las secuencias. Con los permisos de
I-1 a I-9 el usuario de ejecución no podía volcar la base (le faltaba leer `alembic_version`
y las secuencias de las columnas identidad). Se agregan solo permisos de LECTURA: no puede
escribir en `alembic_version` ni cambiar secuencias.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-23
"""

import re

from alembic import context, op

from app.config import Settings

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _runtime_role() -> str:
    role = context.config.attributes.get("runtime_role") or Settings().db_runtime_role
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise RuntimeError("Rol de ejecución inválido")
    return role


def upgrade() -> None:
    app = _runtime_role()
    op.execute(f"GRANT SELECT ON alembic_version TO {app}")
    op.execute(f"GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {app}")


def downgrade() -> None:
    app = _runtime_role()
    # El rol ya se validó como identificador simple (_runtime_role).
    op.execute(f"REVOKE SELECT ON ALL SEQUENCES IN SCHEMA public FROM {app}")  # noqa: S608
    op.execute(f"REVOKE SELECT ON alembic_version FROM {app}")  # noqa: S608
