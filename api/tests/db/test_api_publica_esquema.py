"""Test de esquema: la respuesta pública no expone código INV, IDs, teléfonos, categorías,
mesa, nota ni roles (contrato 07; criterio de I-4)."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from app.esquemas import ConsultaPublica, RespuestaGuardada, RespuestaPublica
from app.estado import MX
from tests.db.util import invitacion_con_enlace

LOOKUP = "/api/v1/public/invitation/lookup"
RESPONSE = "/api/v1/public/invitation/response"
CLAVES_CONSULTA = {
    "nombre_mostrar",
    "pases",
    "fecha_limite",
    "fecha_limite_mostrar",
    "estado",
    "abierta_hasta",
    "respuesta",
}
CLAVES_RESPUESTA = {"asiste", "confirmados", "alergias", "mensaje", "actualizada"}


def test_los_modelos_solo_tienen_los_campos_del_contrato() -> None:
    assert set(ConsultaPublica.model_fields) == CLAVES_CONSULTA
    assert set(RespuestaPublica.model_fields) == CLAVES_RESPUESTA
    assert set(RespuestaGuardada.model_fields) == {"respuesta"}


@pytest.fixture
def completa(api):  # noqa: ANN001, ANN201
    """Invitación con TODOS los campos internos llenos (ficticios) y dos roles."""
    inv = invitacion_con_enlace(
        api.engine,
        api.llaves,
        codigo="INV-987",
        no_planner=77,
        nombre_mostrar="Familia Muestra",
        adultos=2,
        ninos_autorizados=1,
        infantes=1,
        pases_planner_original=3,
        lado="Novio",
        grupo="Trabajo",
        mesa=12,
        nota_interna="Nota interna ficticia XYZ",
        telefono_principal="+12025550147",
        contacto_alterno_nombre="Contacto Ficticio QRS",
        contacto_alterno_tel="+12025550188",
    )
    with api.engine.begin() as conn:
        conn.execute(
            text("INSERT INTO invitacion_rol VALUES (:i, 'Padrinos de arras'), (:i, 'Paje')"),
            {"i": inv["id"]},
        )
    return inv


PROHIBIDOS = [
    "INV-987",
    "Novio",
    "Trabajo",
    "Nota interna ficticia XYZ",
    "+12025550147",
    "+12025550188",
    "Contacto Ficticio QRS",
    "Padrinos de arras",
    "Paje",
    "codigo",
    "telefono",
    "mesa",
    "nota",
    "lado",
    "grupo",
    "rol",
    "infantes",
    "invitacion_id",
    '"id"',
    "no_planner",
    "origen",
    "actor",
    "numero",
    "vigente",
    "hmac",
    "llave",
]


@pytest.mark.parametrize("instante", ["abierta", "cerrada", "congelada"])
def test_consulta_no_expone_datos_internos(api, reloj, completa, instante: str) -> None:  # noqa: ANN001
    api.post(
        RESPONSE,
        json={
            "token": completa["token"],
            "asiste": True,
            "confirmados": 3,
            "alergias": "Ninguna",
            "mensaje": "Hola",
        },
    )
    reloj.ahora = {
        "abierta": reloj.ahora,
        "cerrada": datetime(2027, 1, 31, tzinfo=MX),
        "congelada": datetime(2027, 2, 6, tzinfo=MX) + timedelta(days=1),
    }[instante]
    r = api.post(LOOKUP, json={"token": completa["token"]})
    datos = r.json()
    assert set(datos) == CLAVES_CONSULTA
    assert set(datos["respuesta"]) == CLAVES_RESPUESTA
    assert datos["estado"] == instante
    for prohibido in PROHIBIDOS:
        assert prohibido not in r.text, prohibido
    assert str(completa["id"]) not in [str(v) for v in datos.values()]


def test_respuesta_guardada_no_expone_datos_internos(api, completa) -> None:  # noqa: ANN001
    r = api.post(RESPONSE, json={"token": completa["token"], "asiste": True, "confirmados": 1})
    assert set(r.json()) == {"respuesta"} and set(r.json()["respuesta"]) == CLAVES_RESPUESTA
    for prohibido in PROHIBIDOS:
        assert prohibido not in r.text, prohibido
