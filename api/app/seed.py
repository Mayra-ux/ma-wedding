"""Datos de desarrollo 100 % FICTICIOS (ADR 0010). Sin teléfonos.

Se cargan con el usuario de ejecución. Es idempotente: si ya existe INV-901, no hace nada.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invitacion, InvitacionRol
from app.respuestas import registrar_respuesta

INVITACIONES = (
    # codigo, nombre, adultos, niños, infantes, lado, grupo, roles
    ("INV-901", "Familia Ejemplo", 2, 0, 0, "Novia", "Familia", ("Padrinos de lazo",)),
    ("INV-902", "Familia Prueba", 3, 1, 1, "Novio", "Familia", ()),
    ("INV-903", "Amigos Demo", 2, 0, 0, "Ambos", "Amigos", ("Dama de honor", "Ofrendas")),
    ("INV-904", "Compañía Ficticia", 1, 0, 0, "Novio", "Trabajo", ()),
    ("INV-905", "Invitado Muestra", 1, 0, 0, "Novia", "Otro", ()),
)


def seed(session: Session) -> int:
    if session.scalar(select(Invitacion.id).where(Invitacion.codigo == "INV-901")):
        return 0
    creadas = []
    for codigo, nombre, adultos, ninos, infantes, lado, grupo, roles in INVITACIONES:
        inv = Invitacion(
            codigo=codigo,
            nombre_mostrar=nombre,
            adultos=adultos,
            ninos_autorizados=ninos,
            infantes=infantes,
            lado=lado,
            grupo=grupo,
        )
        session.add(inv)
        session.flush()
        session.add_all(InvitacionRol(invitacion_id=inv.id, rol=r) for r in roles)
        creadas.append(inv)
    # Una respuesta ficticia para ver el historial.
    registrar_respuesta(
        session,
        creadas[0].id,
        asiste=True,
        confirmados=2,
        alergias=None,
        mensaje="Mensaje de prueba",
        origen="invitado",
    )
    return len(creadas)
