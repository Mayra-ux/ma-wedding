"""Límites, encabezados, CORS y errores que no necesitan DB (fase I-4)."""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.limites import LimitadorVentana
from app.main import create_app

ORIGEN = "https://ma-wedding-six.vercel.app"
LOOKUP = "/api/v1/public/invitation/lookup"
RESPONSE = "/api/v1/public/invitation/response"


@pytest.fixture
def cliente() -> TestClient:
    return TestClient(create_app(Settings(invitation_origin=ORIGEN)), raise_server_exceptions=False)


# ------------------------------------------------------------------ limitador
def test_ventana_deslizante_y_reintento() -> None:
    t = [0.0]
    lim = LimitadorVentana(3, ventana_s=3600, reloj=lambda: t[0])
    assert [lim.permitir("a")[0] for _ in range(3)] == [True] * 3
    assert lim.permitir("a") == (False, 3600)
    assert lim.permitir("b")[0] is True  # claves independientes
    t[0] = 1800
    assert lim.permitir("a") == (False, 1800)
    t[0] = 3600  # el primer evento sale de la ventana
    assert lim.permitir("a")[0] is True


def test_tope_de_claves() -> None:
    lim = LimitadorVentana(1, max_claves=100)
    for i in range(1000):
        lim.permitir(i)
    assert len(lim.claves()) <= 100


# ------------------------------------------------------------------ cuerpo y formato
def test_cuerpo_mayor_a_4kb_413(cliente: TestClient) -> None:
    grande = json.dumps({"token": "A" * 22, "x": "y" * 4100}).encode()
    r = cliente.post(LOOKUP, content=grande, headers={"content-type": "application/json"})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "cuerpo_demasiado_grande"


def test_cuerpo_sin_content_length_413(cliente: TestClient) -> None:
    def trozos():  # noqa: ANN202  (envío por partes: sin Content-Length)
        for _ in range(5):
            yield b" " * 1000
        yield b'{"token": "x"}'

    r = cliente.post(LOOKUP, content=trozos(), headers={"content-type": "application/json"})
    assert r.status_code == 413


@pytest.mark.parametrize(
    ("ruta", "cuerpo"),
    [
        (LOOKUP, b"no es json"),
        (LOOKUP, b"{}"),
        (LOOKUP, b'{"token": 123}'),
        (LOOKUP, b'{"token": "x", "pases": 9}'),  # campo de más (B3)
        (RESPONSE, b'{"token": "x", "asiste": "true", "confirmados": 1}'),  # tipo estricto
        (RESPONSE, b'{"token": "x", "asiste": true, "confirmados": "2"}'),
        (RESPONSE, b'{"token": "x", "asiste": true, "confirmados": 1, "ninos": 2}'),
        (RESPONSE, b'{"token": "x", "asiste": true, "confirmados": true}'),
    ],
)
def test_solicitud_invalida_400_sin_repetir_la_entrada(
    cliente: TestClient, ruta: str, cuerpo: bytes
) -> None:
    r = cliente.post(ruta, content=cuerpo, headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert r.json() == {
        "error": {"code": "solicitud_invalida", "message": "La solicitud no es válida."}
    }


@pytest.mark.parametrize(
    ("campo", "valor", "motivo"),
    [
        ("alergias", "a" * 201, "demasiado_largo"),
        ("mensaje", "m" * 501, "demasiado_largo"),
        ("mensaje", "hola\x00", "caracteres_no_permitidos"),
        ("alergias", "nuez\x1b[31m", "caracteres_no_permitidos"),
        ("mensaje", "a\rb", "caracteres_no_permitidos"),
        ("mensaje", "a\x85b", "caracteres_no_permitidos"),
    ],
)
def test_validacion_422_por_campo(cliente: TestClient, campo: str, valor: str, motivo: str) -> None:
    r = cliente.post(RESPONSE, json={"token": "x", "asiste": True, "confirmados": 1, campo: valor})
    assert r.status_code == 422
    assert r.json()["error"] == {
        "code": "validacion",
        "message": "Revisa los datos enviados.",
        "fields": {campo: motivo},
    }
    assert valor not in r.text


def test_validacion_reporta_ambos_campos(cliente: TestClient) -> None:
    r = cliente.post(
        RESPONSE,
        json={
            "token": "x",
            "asiste": True,
            "confirmados": 1,
            "alergias": "a" * 201,
            "mensaje": "m" * 501,
        },
    )
    assert r.json()["error"]["fields"] == {
        "alergias": "demasiado_largo",
        "mensaje": "demasiado_largo",
    }


def test_token_en_la_url_no_existe(cliente: TestClient) -> None:
    assert cliente.get(LOOKUP + "?token=AAAAAAAAAAAAAAAAAAAAAA").status_code == 405
    assert (
        cliente.post("/api/v1/public/invitation/lookup/AAAAAAAAAAAAAAAAAAAAAA").status_code == 404
    )


# ------------------------------------------------------------------ encabezados
ESPERADOS = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
}


@pytest.mark.parametrize(
    ("metodo", "ruta", "kwargs", "status"),
    [
        ("get", "/health", {}, 200),
        ("post", LOOKUP, {"content": b"x"}, 400),
        ("post", LOOKUP, {"content": b"x" * 5000}, 413),
        ("get", "/no-existe", {}, 404),
        ("post", LOOKUP, {"json": {"token": "AAAAAAAAAAAAAAAAAAAAAA"}}, 500),  # sin DB ni llaves
    ],
)
def test_encabezados_en_toda_respuesta(
    cliente: TestClient, metodo: str, ruta: str, kwargs: dict, status: int
) -> None:
    r = getattr(cliente, metodo)(ruta, **kwargs)
    assert r.status_code == status
    for k, v in ESPERADOS.items():
        assert r.headers[k] == v, k
    assert len(r.headers["x-request-id"]) == 32
    assert "strict-transport-security" not in r.headers  # SECURITY_HSTS=false
    assert "server" not in r.headers


def test_error_interno_sin_traza(cliente: TestClient) -> None:
    r = cliente.post(LOOKUP, json={"token": "AAAAAAAAAAAAAAAAAAAAAA"})
    assert r.json() == {
        "error": {"code": "error_interno", "message": "Ocurrió un error. Intenta de nuevo."}
    }


def test_hsts_solo_si_se_activa() -> None:
    c = TestClient(create_app(Settings(security_hsts=True)))
    assert c.get("/health").headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )


# ------------------------------------------------------------------ CORS
def test_cors_origen_permitido(cliente: TestClient) -> None:
    pre = cliente.options(
        LOOKUP,
        headers={
            "origin": ORIGEN,
            "access-control-request-method": "POST",
            "access-control-request-headers": "content-type",
        },
    )
    assert pre.status_code == 200
    assert pre.headers["access-control-allow-origin"] == ORIGEN
    assert "access-control-allow-credentials" not in pre.headers
    assert "POST" in pre.headers["access-control-allow-methods"]
    r = cliente.post(LOOKUP, content=b"x", headers={"origin": ORIGEN})
    assert r.headers["access-control-allow-origin"] == ORIGEN


@pytest.mark.parametrize("origen", ["https://otro.example", "http://ma-wedding-six.vercel.app"])
def test_cors_otro_origen_sin_permiso(cliente: TestClient, origen: str) -> None:
    pre = cliente.options(
        LOOKUP, headers={"origin": origen, "access-control-request-method": "POST"}
    )
    assert "access-control-allow-origin" not in pre.headers
    r = cliente.post(LOOKUP, content=b"x", headers={"origin": origen})
    assert "access-control-allow-origin" not in r.headers


def test_cors_no_aplica_fuera_de_la_api_publica(cliente: TestClient) -> None:
    r = cliente.get("/health", headers={"origin": ORIGEN})
    assert "access-control-allow-origin" not in r.headers


# ------------------------------------------------------------------ límite por IP
def test_limite_por_ip_429(monkeypatch: pytest.MonkeyPatch) -> None:
    c = TestClient(create_app(Settings(rate_limit_ip_per_hour=300)))
    codigos = [c.post(LOOKUP, content=b"{}").status_code for _ in range(300)]
    assert set(codigos) == {400}
    r = c.post(LOOKUP, content=b"{}")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "demasiadas_solicitudes"
    assert int(r.headers["retry-after"]) > 0
    assert c.get("/health").status_code == 200  # el límite solo cubre la API pública
