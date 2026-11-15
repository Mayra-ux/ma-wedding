"""API pública (I-4) con la DB de pruebas y reloj simulado. Datos ficticios."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.enlaces import archivar_invitacion, revocar_enlace
from app.estado import MX
from tests.db.util import invitacion_con_enlace, versiones

LOOKUP = "/api/v1/public/invitation/lookup"
RESPONSE = "/api/v1/public/invitation/response"
CIERRE = datetime(2027, 1, 31, 0, 0, tzinfo=MX)  # ADR 0025
CONGELA = datetime(2027, 3, 7, 0, 0, tzinfo=MX)
S = timedelta(seconds=1)


def _inv(api, **campos):  # noqa: ANN001, ANN202
    return invitacion_con_enlace(api.engine, api.llaves, **campos)


def _responder(api, token: str, asiste: bool = True, confirmados: int = 2, **extra):  # noqa: ANN001, ANN202
    return api.post(
        RESPONSE, json={"token": token, "asiste": asiste, "confirmados": confirmados} | extra
    )


def _sql(api, sql: str, **params) -> None:  # noqa: ANN001
    with api.engine.begin() as conn:
        conn.execute(text(sql), params)


# ------------------------------------------------------------------ estados
def test_abierta_sin_respuesta(api) -> None:  # noqa: ANN001
    inv = _inv(api)
    r = api.post(LOOKUP, json={"token": inv["token"]})
    assert r.status_code == 200
    assert r.json() == {
        "nombre_mostrar": "Familia Ejemplo",
        "pases": 3,
        "fecha_limite": "2027-01-31T00:00:00-06:00",
        "fecha_limite_mostrar": "2027-01-30",
        "estado": "abierta",
        "abierta_hasta": "2027-01-31T00:00:00-06:00",
        "respuesta": None,
    }
    assert r.headers["cache-control"] == "no-store"


def test_abierta_con_respuesta(api) -> None:  # noqa: ANN001
    inv = _inv(api)
    r1 = _responder(api, inv["token"], True, 2, alergias="  Nueces  ", mensaje="¡Felicidades!")
    assert r1.status_code == 200
    guardada = r1.json()["respuesta"]
    assert {k: guardada[k] for k in ("asiste", "confirmados", "alergias", "mensaje")} == {
        "asiste": True,
        "confirmados": 2,
        "alergias": "Nueces",
        "mensaje": "¡Felicidades!",
    }
    assert guardada["actualizada"].endswith("-06:00")
    r = api.post(LOOKUP, json={"token": inv["token"]}).json()
    assert r["estado"] == "abierta" and r["respuesta"] == guardada


@pytest.mark.parametrize("con_respuesta", [False, True])
def test_cerrada(api, reloj, con_respuesta: bool) -> None:  # noqa: ANN001
    inv = _inv(api)
    if con_respuesta:
        assert _responder(api, inv["token"]).status_code == 200
    reloj.ahora = CIERRE
    r = api.post(LOOKUP, json={"token": inv["token"]}).json()
    assert r["estado"] == "cerrada" and r["abierta_hasta"] is None
    assert (r["respuesta"] is not None) is con_respuesta
    assert r["fecha_limite"] == "2027-01-31T00:00:00-06:00"  # siempre la global (C7)
    nuevo = _responder(api, inv["token"], True, 1)
    assert nuevo.status_code == 409
    assert nuevo.json()["error"]["code"] == "plazo_cerrado"
    assert len(versiones(api.engine, inv["id"])) == (1 if con_respuesta else 0)


def test_desbloqueada_y_vuelve_a_cerrada(api, reloj) -> None:  # noqa: ANN001
    inv = _inv(api)
    hasta = CIERRE + timedelta(days=2)
    _sql(api, "UPDATE invitacion SET desbloqueada_hasta = :h WHERE id = :i", h=hasta, i=inv["id"])
    reloj.ahora = CIERRE + timedelta(hours=1)
    r = api.post(LOOKUP, json={"token": inv["token"]}).json()
    assert r["estado"] == "abierta"
    assert r["abierta_hasta"] == "2027-02-02T00:00:00-06:00"
    assert r["fecha_limite"] == "2027-01-31T00:00:00-06:00"  # el mensaje (c) usa la global
    assert _responder(api, inv["token"]).status_code == 200
    reloj.ahora = hasta
    assert api.post(LOOKUP, json={"token": inv["token"]}).json()["estado"] == "cerrada"
    assert _responder(api, inv["token"], True, 1).status_code == 409


@pytest.mark.parametrize("con_respuesta", [False, True])
def test_congelada(api, reloj, con_respuesta: bool) -> None:  # noqa: ANN001
    inv = _inv(api)
    if con_respuesta:
        _responder(api, inv["token"])
    # Aunque tuviera un desbloqueo, el congelamiento gana.
    _sql(
        api,
        "UPDATE invitacion SET desbloqueada_hasta = :h WHERE id = :i",
        h=CONGELA + timedelta(days=1),
        i=inv["id"],
    )
    reloj.ahora = CONGELA
    r = api.post(LOOKUP, json={"token": inv["token"]}).json()
    assert r["estado"] == "congelada" and r["abierta_hasta"] is None
    assert (r["respuesta"] is not None) is con_respuesta
    assert _responder(api, inv["token"], True, 1).json()["error"]["code"] == "plazo_cerrado"


def test_cierre_exacto_en_la_api(api, reloj) -> None:  # noqa: ANN001
    inv = _inv(api)
    reloj.ahora = CIERRE - S
    assert api.post(LOOKUP, json={"token": inv["token"]}).json()["estado"] == "abierta"
    assert _responder(api, inv["token"]).status_code == 200
    reloj.ahora = CIERRE
    assert api.post(LOOKUP, json={"token": inv["token"]}).json()["estado"] == "cerrada"
    assert _responder(api, inv["token"]).status_code == 409


# ------------------------------------------------------------------ 404 idénticos
def test_invalido_revocado_y_archivado_cuerpos_identicos(api) -> None:  # noqa: ANN001
    revocada = _inv(api)
    archivada = _inv(api)
    with Session(api.engine) as s, s.begin():
        revocar_enlace(s, revocada["id"])
        archivar_invitacion(s, archivada["id"])
    casos = {
        "inexistente": "AAAAAAAAAAAAAAAAAAAAAA",
        "mal_formado": "esto-no-es-un-token",
        "no_canonico": "A" * 21 + "B",
        "revocado": revocada["token"],
        "archivado": archivada["token"],
    }
    for ruta, cuerpo in ((LOOKUP, {}), (RESPONSE, {"asiste": True, "confirmados": 1})):
        respuestas = {n: api.post(ruta, json={"token": t} | cuerpo) for n, t in casos.items()}
        assert {r.status_code for r in respuestas.values()} == {404}
        assert {r.content for r in respuestas.values()} == {
            '{"error":{"code":"enlace_no_valido","message":"Este enlace no es válido."}}'.encode()
        }
        sin_id = [
            {k: v for k, v in r.headers.items() if k != "x-request-id"} for r in respuestas.values()
        ]
        assert all(h == sin_id[0] for h in sin_id)


# ------------------------------------------------------------------ validaciones
@pytest.mark.parametrize(
    ("asiste", "confirmados"),
    [(True, 0), (True, 4), (True, -1), (True, 10**6), (False, 1), (False, -1)],
)
def test_confirmados_fuera_de_rango_422_sin_escribir(api, asiste: bool, confirmados: int) -> None:  # noqa: ANN001
    inv = _inv(api)  # 3 pases
    r = _responder(api, inv["token"], asiste, confirmados)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "confirmados_fuera_de_rango"
    assert versiones(api.engine, inv["id"]) == []


def test_no_asiste_vacia_alergias_y_conserva_mensaje(api) -> None:  # noqa: ANN001
    inv = _inv(api)
    r = _responder(api, inv["token"], False, 0, alergias="Mariscos", mensaje="Los queremos")
    assert r.status_code == 200
    resp = r.json()["respuesta"]
    assert (resp["asiste"], resp["confirmados"], resp["alergias"], resp["mensaje"]) == (
        False,
        0,
        None,
        "Los queremos",
    )
    assert versiones(api.engine, inv["id"]) == [
        (1, True, False, 0, None, "Los queremos", "invitado")
    ]


def test_limites_exactos_de_texto(api) -> None:  # noqa: ANN001
    inv = _inv(api)
    r = _responder(api, inv["token"], True, 1, alergias="á" * 200, mensaje="é" * 500)
    assert r.status_code == 200
    r = _responder(api, inv["token"], True, 1, mensaje="línea 1\n\tlínea 2\r\nlínea 3")
    assert r.json()["respuesta"]["mensaje"] == "línea 1\n\tlínea 2\nlínea 3"
    r = _responder(api, inv["token"], True, 1, alergias="   ", mensaje="")
    assert (r.json()["respuesta"]["alergias"], r.json()["respuesta"]["mensaje"]) == (None, None)


def test_texto_con_html_se_guarda_como_texto(api) -> None:  # noqa: ANN001
    inv = _inv(api)
    r = _responder(api, inv["token"], True, 1, mensaje="<script>alert(1)</script>")
    assert r.json()["respuesta"]["mensaje"] == "<script>alert(1)</script>"
    assert r.headers["content-type"].startswith("application/json")


# ------------------------------------------------------------------ versiones
def test_tres_envios_tres_versiones_una_vigente(api) -> None:  # noqa: ANN001
    inv = _inv(api)
    for confirmados in (1, 3, 2):
        assert _responder(api, inv["token"], True, confirmados).status_code == 200
    filas = versiones(api.engine, inv["id"])
    assert [(f[0], f[1], f[3]) for f in filas] == [(1, False, 1), (2, False, 3), (3, True, 2)]
    assert api.post(LOOKUP, json={"token": inv["token"]}).json()["respuesta"]["confirmados"] == 2


def test_pases_se_leen_bajo_el_bloqueo(api) -> None:  # noqa: ANN001
    inv = _inv(api, adultos=2)
    _sql(api, "UPDATE invitacion SET adultos = 4 WHERE id = :i", i=inv["id"])
    assert _responder(api, inv["token"], True, 4).status_code == 200


# ------------------------------------------------------------------ rate limiting por token
def test_limite_por_token_consultas(api) -> None:  # noqa: ANN001
    inv = _inv(api)
    codigos = [api.post(LOOKUP, json={"token": inv["token"]}).status_code for _ in range(20)]
    assert codigos == [200] * 20
    r = api.post(LOOKUP, json={"token": inv["token"]})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    otro = _inv(api)  # otro token no se ve afectado
    assert api.post(LOOKUP, json={"token": otro["token"]}).status_code == 200


def test_limite_por_token_respuestas(api) -> None:  # noqa: ANN001
    inv = _inv(api)
    assert [_responder(api, inv["token"], True, 1).status_code for _ in range(10)] == [200] * 10
    assert _responder(api, inv["token"], True, 1).status_code == 429
    assert len(versiones(api.engine, inv["id"])) == 10


def test_limite_por_token_tambien_para_inexistentes(api) -> None:  # noqa: ANN001
    falso = "AAAAAAAAAAAAAAAAAAAAAA"
    assert {api.post(LOOKUP, json={"token": falso}).status_code for _ in range(20)} == {404}
    assert api.post(LOOKUP, json={"token": falso}).status_code == 429


def test_la_clave_del_limite_es_el_hmac(api) -> None:  # noqa: ANN001
    inv = _inv(api)
    api.post(LOOKUP, json={"token": inv["token"]})
    claves = api.contexto.limite_consulta.claves()
    assert claves and all(isinstance(c[1], bytes) and len(c[1]) == 32 for c in claves)
    assert inv["token"] not in repr(claves)
