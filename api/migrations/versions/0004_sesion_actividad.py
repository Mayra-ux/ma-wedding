"""Sesiones del panel (I-6): última actividad para el cierre por inactividad (doc 06).

- `ultima_actividad`: la sesión vence tras 8 h sin actividad (además del máximo de 7 días
  de `expira_en`). La API la actualiza como mucho una vez cada pocos minutos.
- El usuario de ejecución solo puede actualizar esa columna (ADR 0019, mínimo privilegio).
- Índice en `expira_en` para borrar sesiones vencidas.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15
"""

import re

from alembic import context, op

from app.config import Settings

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _runtime_role() -> str:
    role = context.config.attributes.get("runtime_role") or Settings().db_runtime_role
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise RuntimeError("Rol de ejecución inválido")
    return role


def upgrade() -> None:
    app = _runtime_role()
    op.execute(
        f"""
        ALTER TABLE sesion_admin
            ADD COLUMN ultima_actividad timestamptz NOT NULL DEFAULT now();
        CREATE INDEX sesion_admin_expira ON sesion_admin (expira_en);
        GRANT UPDATE (ultima_actividad) ON sesion_admin TO {app};
        """
    )


def downgrade() -> None:
    app = _runtime_role()
    op.execute(
        f"""
        REVOKE UPDATE (ultima_actividad) ON sesion_admin FROM {app};
        DROP INDEX IF EXISTS sesion_admin_expira;
        ALTER TABLE sesion_admin DROP COLUMN IF EXISTS ultima_actividad;
        """
    )
