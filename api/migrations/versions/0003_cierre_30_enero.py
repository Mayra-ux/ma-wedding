"""Nueva fecha límite del RSVP (ADR 0025): sábado 30 de enero de 2027, incluido completo.

El plazo cierra cuando ahora ≥ 2027-01-31T00:00:00-06:00. El congelamiento (7 mar 2027) y las
fechas de borrado (5 abr y 4 jun 2027) no cambian. Se hace por migración porque el usuario de
ejecución solo puede leer configuracion_evento (ADR 0019).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-15
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE configuracion_evento SET cierre_plazo = '2027-01-31T00:00:00-06:00' WHERE id = 1"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE configuracion_evento SET cierre_plazo = '2027-02-07T00:00:00-06:00' WHERE id = 1"
    )
