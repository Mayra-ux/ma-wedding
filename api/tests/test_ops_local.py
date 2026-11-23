"""Modo «como producción» en local (compose, perfil prod-local; I-10), revisado sin levantarlo.

- El proxy local sirve la invitación con los MISMOS encabezados de vercel.json.
- La base del modo no publica puertos; la API solo se alcanza por el proxy y solo recibe el
  usuario de ejecución; la API confía en un proxy (TRUSTED_PROXY_HOPS=1).
- Las imágenes de terceros están fijadas por digest.
"""

import json
import re
from pathlib import Path

from tests.test_unico_punto_de_escritura import _servicio, _sin_comentarios

REPO = Path(__file__).resolve().parents[2]
NGINX = (REPO / "ops" / "local" / "nginx.conf").read_text(encoding="utf-8")
VERCEL = json.loads((REPO / "invitacion" / "vercel.json").read_text(encoding="utf-8"))


def _encabezados_nginx(bloque: str) -> dict[str, str]:
    return dict(re.findall(r'add_header\s+(\S+)\s+"([^"]*)"\s+always;', bloque))


def test_nginx_replica_los_encabezados_de_vercel() -> None:
    generales = next(r for r in VERCEL["headers"] if r["source"] == "/(.*)")
    esperados = {h["key"]: h["value"] for h in generales["headers"]}
    invitacion = NGINX.split("listen 8080;")[1].split("location")[0]
    assert _encabezados_nginx(invitacion) == esperados
    imagenes = NGINX.split(r"location ~* \.(webp|svg|jpg)$")[1].split("}")[0]
    assert _encabezados_nginx(imagenes) == esperados | {"Cache-Control": "public, max-age=86400"}


def test_el_proxy_agrega_la_ip_del_cliente_a_la_derecha() -> None:
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in NGINX
    assert "access_log off;" in NGINX and "server_tokens off;" in NGINX


def test_servicios_del_modo_como_produccion() -> None:
    db = _sin_comentarios(_servicio("db-prod"))
    assert not re.search(r"^\s+ports:", db, re.MULTILINE)
    api = _sin_comentarios(_servicio("api-prod"))
    assert not re.search(r"^\s+ports:", api, re.MULTILINE)  # solo por el proxy
    assert "MIGRATION_DATABASE_URL" not in api
    assert 'TRUSTED_PROXY_HOPS: "1"' in api and 'SECURITY_HSTS: "false"' in api
    proxy = _sin_comentarios(_servicio("proxy-prod"))
    assert re.search(r"image: nginx:[\d.]+-alpine@sha256:[0-9a-f]{64}", proxy)
    assert '"127.0.0.1:8000:8000"' in proxy
    assert '"127.0.0.1:${INVITACION_PUERTO:-8080}:8080"' in proxy
    assert "MIGRATION_DATABASE_URL" in _sin_comentarios(_servicio("migrate-prod"))
