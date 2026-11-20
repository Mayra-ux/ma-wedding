"""Congelamiento por rol y recordatorios (I-7; ADR 0026 y 0027).

- Invitados: congelamiento el sábado 6 feb 2027 00:00 (−06:00). Desde ese instante ningún
  invitado confirma ni cambia nada, aunque tenga un desbloqueo. La fecha límite (30 ene) y las
  fechas de borrado no cambian.
- Planner: cierre propio `cierre_planner` (7 mar 2027 00:00 −06:00): hasta entonces puede
  marcar recordatorios; después, solo lectura. Configurable por migración.
- Novios: sin congelamiento (lo aplica la API).
- `recordatorio_enviado`: historial de recordatorios sin enlace (tipo y destino; nunca el
  teléfono). El usuario de ejecución solo inserta, lee y borra (purga).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-20
"""

import re

from alembic import context, op

from app.config import Settings

revision = "0005"
down_revision = "0004"
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
        """
        UPDATE configuracion_evento
            SET congelamiento = '2027-02-06T00:00:00-06:00' WHERE id = 1;
        ALTER TABLE configuracion_evento
            ADD COLUMN cierre_planner timestamptz NOT NULL
                DEFAULT '2027-03-07T00:00:00-06:00',
            ADD CONSTRAINT configuracion_orden_planner CHECK (
                congelamiento <= cierre_planner
                AND (cierre_planner AT TIME ZONE 'UTC')::date < fecha_borrado_1
            );

        CREATE TABLE recordatorio_enviado (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            invitacion_id bigint NOT NULL REFERENCES invitacion (id) ON DELETE CASCADE,
            tipo          text NOT NULL
                CONSTRAINT recordatorio_tipo_catalogo CHECK (tipo IN ('confirmar', 'evento')),
            destino       text NOT NULL
                CONSTRAINT recordatorio_destino_catalogo
                CHECK (destino IN ('principal', 'alterno')),
            actor         varchar(254) NOT NULL,
            enviado_en    timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX recordatorio_por_invitacion ON recordatorio_enviado (invitacion_id);
        REVOKE ALL ON recordatorio_enviado FROM PUBLIC;
        """
    )
    # El rol ya se validó como identificador simple (_runtime_role).
    op.execute(f"GRANT SELECT, INSERT, DELETE ON recordatorio_enviado TO {app}")


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS recordatorio_enviado;
        ALTER TABLE configuracion_evento
            DROP CONSTRAINT IF EXISTS configuracion_orden_planner,
            DROP COLUMN IF EXISTS cierre_planner;
        UPDATE configuracion_evento
            SET congelamiento = '2027-03-07T00:00:00-06:00' WHERE id = 1;
        """
    )
