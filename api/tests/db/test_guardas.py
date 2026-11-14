"""Guarda en tiempo de ejecución: la aplicación no borra invitaciones (las archiva)."""

import pytest
from sqlalchemy import Connection, delete, select
from sqlalchemy.orm import Session

from app.guardas import PURGA, BorradoDeInvitacionProhibido
from app.models import Invitacion
from app.respuestas import bloquear_invitacion


def _sesion(conn: Connection) -> Session:
    return Session(bind=conn, join_transaction_mode="create_savepoint")


def _inv(s: Session) -> Invitacion:
    inv = Invitacion(codigo="INV-777", nombre_mostrar="Familia Ejemplo", adultos=1)
    s.add(inv)
    s.flush()
    return inv


def test_session_delete_bloqueado(app_conn: Connection) -> None:
    s = _sesion(app_conn)
    inv = _inv(s)
    s.delete(inv)
    with pytest.raises(BorradoDeInvitacionProhibido):
        s.flush()


def test_sentencia_delete_bloqueada(app_conn: Connection) -> None:
    s = _sesion(app_conn)
    _inv(s)
    with pytest.raises(BorradoDeInvitacionProhibido):
        s.execute(delete(Invitacion).where(Invitacion.codigo == "INV-777"))


def test_purga_si_puede_borrar(app_conn: Connection) -> None:
    s = _sesion(app_conn)
    inv = _inv(s)
    s.info[PURGA] = True
    s.delete(inv)
    s.flush()
    assert s.scalar(select(Invitacion).where(Invitacion.codigo == "INV-777")) is None


def test_bloquear_invitacion_usa_for_update(app_conn: Connection) -> None:
    s = _sesion(app_conn)
    inv = _inv(s)
    sql: list[str] = []

    from sqlalchemy import event

    @event.listens_for(app_conn, "before_cursor_execute")
    def _capturar(conn, cursor, statement, *args):  # noqa: ANN001, ANN202
        sql.append(statement)

    bloquear_invitacion(s, inv.id)
    event.remove(app_conn, "before_cursor_execute", _capturar)
    assert any("FOR UPDATE" in q for q in sql)
