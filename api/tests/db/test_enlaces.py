"""Enlaces (fase I-3): generar, consultar, regenerar, revocar, archivar y buscar por token."""

import re

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.enlaces import (
    Archivada,
    EnlaceNoValido,
    RequiereRevision,
    SinEnlaceActivo,
    YaArchivada,
    YaTieneEnlace,
    archivar_invitacion,
    buscar_por_token,
    generar_enlace,
    obtener_enlace,
    regenerar_enlace,
    revocar_enlace,
)
from app.models import Enlace, Invitacion
from app.tokens import hmac_token, parsear_token
from tests.db.util import llaves_de_prueba, nueva_invitacion

ORIGEN = "https://ma-wedding-six.vercel.app"  # pruebas en la nube (no se envía a invitados)
URL_RE = re.compile(r"^https://ma-wedding-six\.vercel\.app/#t=[A-Za-z0-9_-]{22}$")


@pytest.fixture
def llaves():
    return llaves_de_prueba(("k1",))


def _inv(sesion: Session, **campos: object) -> int:
    return nueva_invitacion(sesion.connection(), **campos)


def _no_valido(sesion: Session, token: str, llaves) -> EnlaceNoValido:  # noqa: ANN001
    with pytest.raises(EnlaceNoValido) as info:
        buscar_por_token(sesion, token, llaves)
    return info.value


def test_generar_y_buscar(sesion: Session, llaves) -> None:  # noqa: ANN001
    inv = _inv(sesion)
    enlace = generar_enlace(sesion, inv, llaves, ORIGEN)
    assert URL_RE.fullmatch(enlace.url)
    assert enlace.url == f"{ORIGEN}/#t={enlace.token.valor}"
    assert buscar_por_token(sesion, enlace.token.valor, llaves).id == inv


def test_en_la_db_solo_hmac_y_copia_cifrada_con_id_de_llave(sesion: Session, llaves) -> None:  # noqa: ANN001
    inv = _inv(sesion)
    enlace = generar_enlace(sesion, inv, llaves, ORIGEN)
    fila = sesion.scalar(select(Enlace).where(Enlace.invitacion_id == inv))
    assert fila.hmac_token == hmac_token(llaves.hash_actual, enlace.token.raw)
    assert len(fila.hmac_token) == 32
    assert len(fila.token_cifrado) == 44
    assert fila.id_llave == "k1"
    assert enlace.token.raw not in fila.token_cifrado


def test_obtener_enlace_descifra_el_mismo_token(sesion: Session, llaves) -> None:  # noqa: ANN001
    inv = _inv(sesion)
    generado = generar_enlace(sesion, inv, llaves, ORIGEN)
    consultado = obtener_enlace(sesion, inv, llaves, ORIGEN)
    assert consultado.url == generado.url
    assert URL_RE.fullmatch(consultado.url)


def test_url_local(sesion: Session, llaves) -> None:  # noqa: ANN001
    enlace = generar_enlace(sesion, _inv(sesion), llaves, "http://localhost:8080")
    assert re.fullmatch(r"http://localhost:8080/#t=[A-Za-z0-9_-]{22}", enlace.url)


# ------------------------------------------------------------------ 409
def test_no_se_genera_para_invitacion_en_revision(sesion: Session, llaves) -> None:  # noqa: ANN001
    inv = _inv(sesion, requiere_revision=True, motivos_revision=["pases_inconsistentes"])
    for operacion in (generar_enlace, regenerar_enlace):
        with pytest.raises(RequiereRevision) as info:
            operacion(sesion, inv, llaves, ORIGEN)
        assert (info.value.codigo, info.value.status) == ("requiere_revision", 409)
    assert sesion.scalar(select(Enlace).where(Enlace.invitacion_id == inv)) is None


def test_no_se_genera_para_invitacion_archivada(sesion: Session, llaves) -> None:  # noqa: ANN001
    inv = _inv(sesion)
    archivar_invitacion(sesion, inv)
    for operacion in (generar_enlace, regenerar_enlace):
        with pytest.raises(Archivada) as info:
            operacion(sesion, inv, llaves, ORIGEN)
        assert (info.value.codigo, info.value.status) == ("archivada", 409)
    assert sesion.scalar(select(Enlace).where(Enlace.invitacion_id == inv)) is None


def test_ya_tiene_enlace(sesion: Session, llaves) -> None:  # noqa: ANN001
    inv = _inv(sesion)
    generar_enlace(sesion, inv, llaves, ORIGEN)
    with pytest.raises(YaTieneEnlace) as info:
        generar_enlace(sesion, inv, llaves, ORIGEN)
    assert (info.value.codigo, info.value.status) == ("ya_tiene_enlace", 409)


# ---------------------------------------------- 404 tras regenerar, revocar o archivar
def test_regenerar_invalida_el_anterior_y_reinicia_envio(sesion: Session, llaves) -> None:  # noqa: ANN001
    inv = _inv(sesion)
    viejo = generar_enlace(sesion, inv, llaves, ORIGEN)
    sesion.execute(
        text(
            "UPDATE invitacion SET enlace_enviado_en = now(), "
            "enlace_enviado_origen = 'whatsapp' WHERE id = :i"
        ),
        {"i": inv},
    )
    nuevo = regenerar_enlace(sesion, inv, llaves, ORIGEN)
    assert nuevo.token.valor != viejo.token.valor
    error = _no_valido(sesion, viejo.token.valor, llaves)
    assert (error.codigo, error.status) == ("enlace_no_valido", 404)
    assert buscar_por_token(sesion, nuevo.token.valor, llaves).id == inv
    fila = sesion.get(Invitacion, inv, populate_existing=True)
    assert fila.enlace_enviado_en is None and fila.enlace_enviado_origen is None
    activos = sesion.scalars(
        select(Enlace).where(Enlace.invitacion_id == inv, Enlace.revocado_en.is_(None))
    ).all()
    assert len(activos) == 1


def test_revocar_invalida_el_token(sesion: Session, llaves) -> None:  # noqa: ANN001
    inv = _inv(sesion)
    enlace = generar_enlace(sesion, inv, llaves, ORIGEN)
    revocar_enlace(sesion, inv)
    _no_valido(sesion, enlace.token.valor, llaves)
    with pytest.raises(SinEnlaceActivo) as info:
        revocar_enlace(sesion, inv)
    assert (info.value.codigo, info.value.status) == ("sin_enlace_activo", 404)
    with pytest.raises(SinEnlaceActivo):
        obtener_enlace(sesion, inv, llaves, ORIGEN)


def test_archivar_revoca_e_invalida_el_token(sesion: Session, llaves) -> None:  # noqa: ANN001
    inv = _inv(sesion)
    enlace = generar_enlace(sesion, inv, llaves, ORIGEN)
    archivar_invitacion(sesion, inv)
    _no_valido(sesion, enlace.token.valor, llaves)
    fila = sesion.scalar(select(Enlace).where(Enlace.invitacion_id == inv))
    assert fila.revocado_en is not None
    with pytest.raises(YaArchivada):
        archivar_invitacion(sesion, inv)


def test_archivada_sin_revocar_tampoco_responde(sesion: Session, llaves) -> None:  # noqa: ANN001
    """Defensa extra: aunque el enlace siguiera activo, una invitación archivada no responde."""
    inv = _inv(sesion)
    enlace = generar_enlace(sesion, inv, llaves, ORIGEN)
    sesion.execute(text("UPDATE invitacion SET archivada_en = now() WHERE id = :i"), {"i": inv})
    _no_valido(sesion, enlace.token.valor, llaves)


def test_respuesta_identica_para_todo_fallo(sesion: Session, llaves) -> None:  # noqa: ANN001
    inv = _inv(sesion)
    revocado = generar_enlace(sesion, inv, llaves, ORIGEN).token.valor
    revocar_enlace(sesion, inv)
    inv2 = _inv(sesion)
    archivado = generar_enlace(sesion, inv2, llaves, ORIGEN).token.valor
    archivar_invitacion(sesion, inv2)
    inexistente = "AAAAAAAAAAAAAAAAAAAAAA"
    assert parsear_token(inexistente) is not None
    casos = [revocado, archivado, inexistente, "mal formado", "", "A" * 21 + "B", None]
    errores = [_no_valido(sesion, c, llaves) for c in casos]
    assert {(type(e), e.codigo, e.status, str(e), e.args) for e in errores} == {
        (EnlaceNoValido, "enlace_no_valido", 404, "enlace_no_valido", ("enlace_no_valido",))
    }


def test_con_otra_llave_de_hash_el_token_no_sirve(sesion: Session, llaves) -> None:  # noqa: ANN001
    enlace = generar_enlace(sesion, _inv(sesion), llaves, ORIGEN)
    _no_valido(sesion, enlace.token.valor, llaves_de_prueba(("k1",)))
