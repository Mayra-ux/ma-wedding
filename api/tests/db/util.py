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


def llaves_de_prueba(
    ids: tuple[str, ...] = ("k1",),
    hash_key: bytes | None = None,
    anterior: bytes | None = None,
    cifrado: dict[str, bytes] | None = None,
):
    """Llaves aleatorias generadas en memoria (nunca se escriben en archivos)."""
    import base64
    import secrets

    from app.tokens import parsear_llaves

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    cifrado = cifrado or {}
    enc = ",".join(f"{k}:{b64(cifrado.get(k) or secrets.token_bytes(32))}" for k in ids)
    return parsear_llaves(
        b64(hash_key or secrets.token_bytes(32)), b64(anterior) if anterior else None, enc
    )


def invitacion_con_enlace(engine, llaves, **campos: object) -> dict:  # noqa: ANN001
    """Crea (y confirma) una invitación ficticia con enlace activo. Devuelve sus datos."""
    from sqlalchemy.orm import Session

    from app.enlaces import generar_enlace

    with Session(engine) as s, s.begin():
        valores = {"nombre_mostrar": "Familia Ejemplo", "adultos": 3} | campos
        inv_id = nueva_invitacion(s.connection(), **valores)
        enlace = generar_enlace(s, inv_id, llaves, "https://ma-wedding-six.vercel.app")
        codigo = s.connection().scalar(
            text("SELECT codigo FROM invitacion WHERE id = :i"), {"i": inv_id}
        )
    return {"id": inv_id, "token": enlace.token.valor, "codigo": codigo, **valores}


def versiones(engine, inv_id: int) -> list[tuple]:  # noqa: ANN001
    with engine.connect() as conn:
        return [
            tuple(f)
            for f in conn.execute(
                text(
                    "SELECT numero, vigente, asiste, confirmados, alergias, mensaje, origen "
                    "FROM version_respuesta WHERE invitacion_id = :i ORDER BY numero"
                ),
                {"i": inv_id},
            )
        ]
