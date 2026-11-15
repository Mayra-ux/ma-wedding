"""El token en claro nunca se guarda ni se registra (ADR 0019, criterio de I-3).

Recorre el ciclo completo (generar, consultar, buscar, regenerar, revocar, archivar, rotar
y fallos) y comprueba que el token, como texto o como sus 16 bytes, no aparece:
1. en ninguna sentencia ni parámetro enviados a Postgres;
2. en ninguna fila de ninguna tabla;
3. en ningún registro de log (DEBUG, incluido el eco de SQLAlchemy con parámetros);
4. en los mensajes de error.
"""

import logging
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, event, text
from sqlalchemy.orm import Session

from app.enlaces import (
    EnlaceNoValido,
    ErrorEnlace,
    archivar_invitacion,
    buscar_por_token,
    generar_enlace,
    obtener_enlace,
    regenerar_enlace,
    revocar_enlace,
    rotar_llaves,
)
from tests.db.util import llaves_de_prueba, nueva_invitacion

TABLAS = (
    "invitacion",
    "invitacion_rol",
    "version_respuesta",
    "enlace",
    "sesion_admin",
    "evento_auditoria",
    "configuracion_evento",
)


@pytest.fixture
def conn_con_eco(base: dict[str, str]) -> Iterator[Connection]:
    """Conexión del usuario de ejecución con eco DEBUG (registra sentencias y parámetros)."""
    engine: Engine = create_engine(base["app"], echo="debug")
    conn = engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()
        engine.dispose()


def _formas(raw: bytes, valor: str) -> list[str]:
    """Representaciones a buscar: texto base64url, hex y repr de los bytes."""
    return [valor, raw.hex(), raw.hex().upper(), repr(raw)]


def test_el_token_no_se_guarda_ni_se_registra(
    conn_con_eco: Connection, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)  # todos los loggers, incluido sqlalchemy.engine
    enviado: list[str] = []

    @event.listens_for(conn_con_eco, "before_cursor_execute")
    def _capturar(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ANN202
        enviado.append(repr(statement))
        enviado.append(repr(parameters))

    llaves = llaves_de_prueba(("k1",))
    nuevas = llaves_de_prueba(
        ("k2", "k1"), cifrado={"k1": llaves.cifrado["k1"]}, anterior=llaves.hash_actual
    )
    s = Session(bind=conn_con_eco, join_transaction_mode="create_savepoint")
    origen = "http://localhost:8080"
    tokens: list = []
    errores: list[str] = []

    a = nueva_invitacion(conn_con_eco)
    b = nueva_invitacion(conn_con_eco)
    t1 = generar_enlace(s, a, llaves, origen)
    tokens.append(t1.token)
    tokens.append(obtener_enlace(s, a, llaves, origen).token)
    buscar_por_token(s, t1.token.valor, llaves)
    t2 = regenerar_enlace(s, a, llaves, origen)
    tokens.append(t2.token)
    for intento in (t1.token.valor, t1.token.valor[:-1] + "A"):
        try:
            buscar_por_token(s, intento, llaves)
        except EnlaceNoValido as exc:
            errores += [str(exc), repr(exc), repr(exc.args)]
    t3 = generar_enlace(s, b, llaves, origen)
    tokens.append(t3.token)
    rotar_llaves(s, nuevas)
    buscar_por_token(s, t3.token.valor, nuevas)
    revocar_enlace(s, a)
    archivar_invitacion(s, b)
    try:
        buscar_por_token(s, t3.token.valor, nuevas)
    except ErrorEnlace as exc:
        errores += [str(exc), repr(exc)]
    errores += [repr(t1), str(t1), repr(t1.token), f"{t1.token}"]
    s.flush()

    # Volcado completo de todas las tablas (row_to_json muestra bytea como \x<hex>).
    volcado = [
        conn_con_eco.execute(
            text(f"SELECT coalesce(json_agg(t)::text, '') FROM {tabla} t")
        ).scalar()
        for tabla in TABLAS
    ]
    logs = [r.getMessage() for r in caplog.records] + [repr(r.args) for r in caplog.records]

    assert enviado and logs and any("enlace" in v for v in volcado)
    for token in tokens:
        for forma in _formas(token.raw, token.valor):
            assert not any(forma in x for x in enviado), "token enviado a Postgres"
            assert not any(forma in x for x in volcado), "token guardado en una tabla"
            assert not any(forma in x for x in logs), "token en un log"
            assert not any(forma in x for x in errores), "token en un mensaje de error"
