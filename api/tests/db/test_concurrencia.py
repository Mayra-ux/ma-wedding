"""Concurrencia: dos respuestas simultáneas para la misma invitación.

La API bloquea la invitación (SELECT … FOR UPDATE) antes de crear la versión
(doc 02, «Concurrencia»). Resultado esperado: exactamente una vigente y
numeración 1, 2 sin huecos ni repetidos.
"""

import threading
import time

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.respuestas import registrar_respuesta
from tests.db.util import nueva_invitacion

pytestmark = pytest.mark.usefixtures("limpiar")


def _invitacion_confirmada(engine: Engine) -> int:
    with engine.begin() as conn:
        return nueva_invitacion(conn, adultos=3)


def _versiones(engine: Engine, inv: int) -> list[tuple[int, bool, int]]:
    with engine.connect() as conn:
        return [
            tuple(f)
            for f in conn.execute(
                text(
                    "SELECT numero, vigente, confirmados FROM version_respuesta "
                    "WHERE invitacion_id = :i ORDER BY numero"
                ),
                {"i": inv},
            )
        ]


def test_dos_respuestas_simultaneas_con_bloqueo(app_engine: Engine) -> None:
    inv = _invitacion_confirmada(app_engine)
    a_tiene_bloqueo = threading.Event()
    errores: list[BaseException] = []
    espera_b: list[float] = []

    def envio_a() -> None:
        try:
            with Session(app_engine) as s, s.begin():
                registrar_respuesta(
                    s,
                    inv,
                    asiste=True,
                    confirmados=1,
                    alergias=None,
                    mensaje=None,
                    origen="invitado",
                )
                a_tiene_bloqueo.set()
                time.sleep(0.6)  # B intenta entrar mientras A sostiene el bloqueo
        except BaseException as exc:  # noqa: BLE001
            errores.append(exc)
            a_tiene_bloqueo.set()

    def envio_b() -> None:
        try:
            a_tiene_bloqueo.wait(5)
            inicio = time.monotonic()
            with Session(app_engine) as s, s.begin():
                registrar_respuesta(
                    s,
                    inv,
                    asiste=True,
                    confirmados=2,
                    alergias=None,
                    mensaje=None,
                    origen="invitado",
                )
            espera_b.append(time.monotonic() - inicio)
        except BaseException as exc:  # noqa: BLE001
            errores.append(exc)

    hilos = [threading.Thread(target=envio_a), threading.Thread(target=envio_b)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(15)

    assert errores == []
    assert espera_b and espera_b[0] >= 0.4, "B debió esperar el bloqueo de A"
    assert _versiones(app_engine, inv) == [(1, False, 1), (2, True, 2)]


def test_sin_bloqueo_la_db_igual_impide_dos_vigentes(app_engine: Engine) -> None:
    """Última defensa: aunque la API olvidara el bloqueo, el índice único parcial rechaza
    la segunda versión vigente (la segunda transacción espera y luego falla)."""
    inv = _invitacion_confirmada(app_engine)
    insertar = text(
        "INSERT INTO version_respuesta (invitacion_id, numero, vigente, asiste, confirmados, "
        "origen) VALUES (:i, :n, true, true, 1, 'invitado')"
    )
    a_inserto = threading.Event()
    resultado_b: list[BaseException | None] = []

    def tx_a() -> None:
        with app_engine.begin() as conn:
            conn.execute(insertar, {"i": inv, "n": 1})
            a_inserto.set()
            time.sleep(0.4)

    def tx_b() -> None:
        a_inserto.wait(5)
        try:
            with app_engine.begin() as conn:
                conn.execute(insertar, {"i": inv, "n": 2})
            resultado_b.append(None)
        except IntegrityError as exc:
            resultado_b.append(exc)

    hilos = [threading.Thread(target=tx_a), threading.Thread(target=tx_b)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(15)

    assert isinstance(resultado_b[0], IntegrityError)
    assert resultado_b[0].orig.sqlstate == "23505"
    assert _versiones(app_engine, inv) == [(1, True, 1)]
