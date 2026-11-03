"""rotate-keys: vuelve a cifrar todas las copias y recalcula los HMAC sin cortar enlaces."""

import secrets

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enlaces import (
    EnlaceNoValido,
    buscar_por_token,
    generar_enlace,
    obtener_enlace,
    revocar_enlace,
    rotar_llaves,
)
from app.models import Enlace
from app.tokens import CopiaIlegible
from tests.db.util import llaves_de_prueba, nueva_invitacion

ORIGEN = "http://localhost:8080"


def _escenario(sesion: Session, llaves) -> tuple[list[int], list[str]]:  # noqa: ANN001
    conn = sesion.connection()
    invs = [nueva_invitacion(conn) for _ in range(3)]
    tokens = [generar_enlace(sesion, i, llaves, ORIGEN).token.valor for i in invs]
    revocar_enlace(sesion, invs[2])  # también se recifran los revocados
    return invs, tokens


def test_rotar_llave_de_cifrado_y_de_hash(sesion: Session) -> None:
    k1, h1 = secrets.token_bytes(32), secrets.token_bytes(32)
    viejas = llaves_de_prueba(("k1",), hash_key=h1, cifrado={"k1": k1})
    invs, tokens = _escenario(sesion, viejas)

    # Paso 1: llave nueva al principio (se conserva k1) y hash nuevo con el anterior en _PREVIOUS.
    transicion = llaves_de_prueba(("k2", "k1"), anterior=h1, cifrado={"k1": k1})
    # Antes de rotar, los enlaces siguen funcionando gracias a la llave de hash anterior.
    assert buscar_por_token(sesion, tokens[0], transicion).id == invs[0]

    # Paso 2: rotate-keys.
    informe = rotar_llaves(sesion, transicion)
    assert (informe.enlaces, informe.recifrados, informe.al_dia) == (3, 3, 0)
    filas = sesion.scalars(select(Enlace).order_by(Enlace.id)).all()
    assert {f.id_llave for f in filas} == {"k2"}

    # Es idempotente.
    assert rotar_llaves(sesion, transicion).al_dia == 3

    # Paso 3: se retiran k1 y la llave de hash anterior; todo sigue funcionando.
    nuevas = llaves_de_prueba(
        ("k2",), hash_key=transicion.hash_actual, cifrado={"k2": transicion.cifrado["k2"]}
    )
    for inv, token in zip(invs[:2], tokens[:2], strict=True):
        assert buscar_por_token(sesion, token, nuevas).id == inv
        assert obtener_enlace(sesion, inv, nuevas, ORIGEN).token.valor == token
    with pytest.raises(EnlaceNoValido):  # el revocado sigue revocado
        buscar_por_token(sesion, tokens[2], nuevas)
    # Con las llaves viejas ya no se encuentra nada.
    with pytest.raises(EnlaceNoValido):
        buscar_por_token(sesion, tokens[0], viejas)


def test_rotacion_atomica_si_falta_una_llave(sesion: Session) -> None:
    viejas = llaves_de_prueba(("k1",))
    _escenario(sesion, viejas)
    sesion.commit()  # libera el savepoint: el escenario queda; el rollback solo deshace la rotación
    antes = [(f.id_llave, f.token_cifrado, f.hmac_token) for f in sesion.scalars(select(Enlace))]
    sin_k1 = llaves_de_prueba(("k2",))  # olvidaron conservar k1
    with pytest.raises(CopiaIlegible):
        rotar_llaves(sesion, sin_k1)
    sesion.rollback()
    despues = [(f.id_llave, f.token_cifrado, f.hmac_token) for f in sesion.scalars(select(Enlace))]
    assert despues == antes
