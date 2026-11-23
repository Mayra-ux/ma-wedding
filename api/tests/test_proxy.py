"""IP del cliente detrás de proxies (I-10; ADR 0030; app/proxy.py).

Prueba del encabezado falsificado: 301 peticiones con `X-Forwarded-For` aleatorio a la
izquierda (lo que escribe el atacante) y la IP real agregada por el proxy a la derecha →
la 301 recibe 429. Y la demostración del problema que corrige: con uvicorn y
`FORWARDED_ALLOW_IPS="*"`, el mismo ataque nunca llega al límite.
"""

import re
import secrets
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import Settings
from app.main import create_app
from app.proxy import ip_del_cliente

ORIGEN = "https://ma-wedding-six.vercel.app"
LOOKUP = "/api/v1/public/invitation/lookup"
REAL = "203.0.113.7"  # TEST-NET-3 (documentación)


def _falsa() -> str:
    return f"198.51.100.{secrets.randbelow(254) + 1}, 10.{secrets.randbelow(255)}.0.1"


@pytest.mark.parametrize(
    ("conexion", "xff", "saltos", "esperada"),
    [
        ("10.0.0.2", [], 0, "10.0.0.2"),
        ("10.0.0.2", ["1.2.3.4"], 0, "10.0.0.2"),  # sin proxies: se ignora el encabezado
        ("10.0.0.2", [f"1.2.3.4, {REAL}"], 1, REAL),  # la de la derecha la puso el proxy
        ("10.0.0.2", [f"1.2.3.4, {REAL}, 10.1.1.1"], 2, REAL),
        ("10.0.0.2", ["1.2.3.4", REAL], 1, REAL),  # varios encabezados se concatenan
        ("10.0.0.2", [], 1, "10.0.0.2"),  # no pasó por el proxy
        ("10.0.0.2", [REAL], 2, "10.0.0.2"),  # menos entradas que proxies
        ("10.0.0.2", ["no-es-ip"], 1, "10.0.0.2"),
        ("10.0.0.2", ["2001:db8::1"], 1, "2001:db8::1"),
    ],
)
def test_ip_del_cliente(conexion: str, xff: list[str], saltos: int, esperada: str) -> None:
    assert ip_del_cliente(conexion, xff, saltos) == esperada


def _cliente(app) -> TestClient:  # noqa: ANN001
    return TestClient(app, raise_server_exceptions=False)


def _settings(saltos: int) -> Settings:
    return Settings(invitation_origin=ORIGEN, trusted_proxy_hops=saltos, rate_limit_ip_per_hour=300)


def test_encabezado_falsificado_301_peticiones_429() -> None:
    cliente = _cliente(create_app(_settings(1)))
    codigos = [
        cliente.post(
            LOOKUP, json={}, headers={"x-forwarded-for": f"{_falsa()}, {REAL}"}
        ).status_code
        for _ in range(301)
    ]
    assert 429 not in codigos[:300]
    assert codigos[300] == 429
    # Otra IP real (otro cliente detrás del mismo proxy) no está limitada.
    otra = cliente.post(LOOKUP, json={}, headers={"x-forwarded-for": f"{_falsa()}, 203.0.113.8"})
    assert otra.status_code != 429


def test_el_limite_del_login_del_panel_tambien_usa_la_ip_real() -> None:
    cliente = _cliente(create_app(_settings(1)))
    login = "/api/v1/auth/google/login"
    codigos = [
        cliente.get(
            login, headers={"x-forwarded-for": f"{_falsa()}, {REAL}"}, follow_redirects=False
        ).status_code
        for _ in range(301)
    ]
    assert codigos[300] == 429


def test_sin_proxies_el_encabezado_no_cambia_nada() -> None:
    cliente = _cliente(create_app(_settings(0)))
    codigos = [
        cliente.post(LOOKUP, json={}, headers={"x-forwarded-for": _falsa()}).status_code
        for _ in range(301)
    ]
    assert codigos[300] == 429  # todas cuentan para la IP de la conexión


def test_demostracion_uvicorn_con_asterisco_es_evadible() -> None:
    """El comportamiento que se corrige: uvicorn confía en la IP de más a la izquierda."""
    app = ProxyHeadersMiddleware(create_app(_settings(0)), trusted_hosts="*")
    cliente = _cliente(app)
    codigos = [
        cliente.post(
            LOOKUP, json={}, headers={"x-forwarded-for": f"{_falsa()}, {REAL}"}
        ).status_code
        for _ in range(301)
    ]
    assert 429 not in codigos  # el atacante nunca llega al límite


def test_la_imagen_desactiva_los_encabezados_de_proxy_de_uvicorn() -> None:
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")
    cmd = next(ln for ln in dockerfile.splitlines() if ln.startswith("CMD"))
    assert '"--no-proxy-headers"' in cmd
    assert '"--proxy-headers"' not in cmd
    assert not re.search(r"^ENV FORWARDED_ALLOW_IPS", dockerfile, re.MULTILINE)
