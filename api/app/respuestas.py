"""Registro de respuestas con bloqueo de la invitación (concurrencia).

Regla (docs/architecture/02-modelo-de-datos.md, «Concurrencia»): antes de crear
una versión de respuesta o de modificar pases, la API bloquea la fila de la
invitación con SELECT … FOR UPDATE. Así dos envíos simultáneos se serializan y
terminan con exactamente una versión vigente y numeración consecutiva.
"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import guardas  # noqa: F401  (guarda contra DELETE de invitaciones)
from app.models import Invitacion, VersionRespuesta


def bloquear_invitacion(session: Session, invitacion_id: int) -> Invitacion:
    """SELECT … FOR UPDATE sobre la invitación. Debe ir dentro de una transacción."""
    return session.execute(
        select(Invitacion).where(Invitacion.id == invitacion_id).with_for_update()
    ).scalar_one()


def registrar_respuesta(
    session: Session,
    invitacion_id: int,
    *,
    asiste: bool,
    confirmados: int,
    alergias: str | None,
    mensaje: str | None,
    origen: str,
    actor: str | None = None,
) -> VersionRespuesta:
    """Crea una versión nueva y la marca como vigente. No hace commit.

    Las reglas de negocio (plazo, rango, vaciado de alergias) se validan en la
    API (fase I-4); la DB es la última defensa.
    """
    bloquear_invitacion(session, invitacion_id)
    ultimo = session.execute(
        select(func.coalesce(func.max(VersionRespuesta.numero), 0)).where(
            VersionRespuesta.invitacion_id == invitacion_id
        )
    ).scalar_one()
    # Primero se retira la vigente anterior y luego se inserta la nueva (índice único parcial).
    session.execute(
        update(VersionRespuesta)
        .where(VersionRespuesta.invitacion_id == invitacion_id, VersionRespuesta.vigente)
        .values(vigente=False)
    )
    version = VersionRespuesta(
        invitacion_id=invitacion_id,
        numero=ultimo + 1,
        vigente=True,
        asiste=asiste,
        confirmados=confirmados,
        alergias=alergias,
        mensaje=mensaje,
        origen=origen,
        actor=actor,
    )
    session.add(version)
    session.flush()
    return version
