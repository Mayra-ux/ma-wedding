"""Ayudantes para los tests de la DB (datos ficticios)."""

import itertools

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

_codigos = itertools.count(100)


def nueva_invitacion(conn: Connection, **campos: object) -> int:
    valores = {
        "codigo": f"INV-{next(_codigos)}",
        "nombre_mostrar": "Familia Ejemplo",
        "adultos": 2,
    } | campos
    cols = ", ".join(valores)
    params = ", ".join(f":{c}" for c in valores)
    return conn.scalar(
        text(f"INSERT INTO invitacion ({cols}) VALUES ({params}) RETURNING id"), valores
    )


def nueva_version(conn: Connection, invitacion_id: int, **campos: object) -> int:
    valores = {
        "invitacion_id": invitacion_id,
        "numero": 1,
        "vigente": True,
        "asiste": True,
        "confirmados": 1,
        "origen": "invitado",
    } | campos
    cols = ", ".join(valores)
    params = ", ".join(f":{c}" for c in valores)
    return conn.scalar(
        text(f"INSERT INTO version_respuesta ({cols}) VALUES ({params}) RETURNING id"), valores
    )


def falla_con(conn: Connection, sqlstate: str, sql: str, params: dict | None = None) -> str:
    """Ejecuta `sql` en un savepoint, exige el SQLSTATE dado y devuelve el mensaje."""
    with pytest.raises(DBAPIError) as info, conn.begin_nested():
        conn.execute(text(sql), params or {})
    assert info.value.orig.sqlstate == sqlstate, info.value.orig
    return str(info.value.orig)
