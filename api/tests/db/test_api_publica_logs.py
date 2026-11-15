"""Los logs de la API no contienen el token ni el nombre usados (criterio de I-4, ADR 0019)."""

import logging

from tests.db.util import invitacion_con_enlace

LOOKUP = "/api/v1/public/invitation/lookup"
RESPONSE = "/api/v1/public/invitation/response"


def test_logs_sin_token_ni_nombre(api, reloj, caplog) -> None:  # noqa: ANN001
    caplog.set_level(logging.DEBUG)  # todos los loggers: app, uvicorn, sqlalchemy, httpx…
    nombre = "Familia Trazable Ficticia"
    inv = invitacion_con_enlace(api.engine, api.llaves, nombre_mostrar=nombre, adultos=2)
    token = inv["token"]
    alergia, mensaje = "Alergia trazable", "Mensaje trazable"

    api.post(LOOKUP, json={"token": token})
    api.post(
        RESPONSE,
        json={
            "token": token,
            "asiste": True,
            "confirmados": 2,
            "alergias": alergia,
            "mensaje": mensaje,
        },
    )
    api.post(RESPONSE, json={"token": token, "asiste": True, "confirmados": 9})  # 422
    api.post(
        RESPONSE, json={"token": token, "asiste": True, "confirmados": 1, "mensaje": "x" * 600}
    )  # 422 validacion
    api.post(LOOKUP, json={"token": token[:-1] + "A"})  # 404
    api.post(LOOKUP, content=b"{no json " + token.encode())  # 400
    from datetime import datetime

    from app.estado import MX

    reloj.ahora = datetime(2027, 2, 8, tzinfo=MX)
    api.post(RESPONSE, json={"token": token, "asiste": False, "confirmados": 0})  # 409

    textos = [r.getMessage() for r in caplog.records] + [repr(r.args) for r in caplog.records]
    acceso = [r.getMessage() for r in caplog.records if r.name == "app.acceso"]
    assert len(acceso) == 7
    assert any(f"inv={inv['codigo']}" in a for a in acceso)  # el código INV sí se permite
    for prohibido in (token, nombre, alergia, mensaje, "testclient"):
        assert not any(prohibido in t for t in textos), prohibido
