"""Las invitaciones no se borran: se archivan (ADR 0017, regla A12).

Solo la purga de datos (fase I-10, módulo `app/purga.py`) puede borrarlas, y debe
marcar la sesión con `session.info["purga"] = True`. Estas guardas cubren el
borrado por ORM (session.delete de una invitación) y por sentencia (delete de
SQLAlchemy sobre el modelo); el SQL de texto lo vigila un test estático
(tests/test_sin_delete_invitacion.py).
"""

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session

from app.models import Invitacion

PURGA = "purga"


class BorradoDeInvitacionProhibido(RuntimeError):
    """Se intentó borrar una invitación fuera de la purga."""


@event.listens_for(Session, "before_flush")
def _bloquear_delete_orm(session: Session, flush_context: object, instances: object) -> None:
    if session.info.get(PURGA):
        return
    if any(isinstance(obj, Invitacion) for obj in session.deleted):
        raise BorradoDeInvitacionProhibido("Las invitaciones se archivan; no se borran.")


@event.listens_for(Session, "do_orm_execute")
def _bloquear_delete_sentencia(state: ORMExecuteState) -> None:
    if not state.is_delete or state.session.info.get(PURGA):
        return
    table = getattr(state.statement, "table", None)
    if getattr(table, "name", None) == Invitacion.__tablename__:
        raise BorradoDeInvitacionProhibido("Las invitaciones se archivan; no se borran.")
