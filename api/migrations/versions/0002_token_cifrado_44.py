"""Copia cifrada del token con longitud exacta (fase I-3).

token_cifrado = nonce (12) ‖ cifrado (16) ‖ etiqueta GCM (16) = 44 bytes (app/tokens.py).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE enlace DROP CONSTRAINT enlace_cifrado_no_vacio;
        ALTER TABLE enlace ADD CONSTRAINT enlace_cifrado_longitud
            CHECK (octet_length(token_cifrado) = 44);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE enlace DROP CONSTRAINT enlace_cifrado_longitud;
        ALTER TABLE enlace ADD CONSTRAINT enlace_cifrado_no_vacio
            CHECK (octet_length(token_cifrado) > 28);
        """
    )
