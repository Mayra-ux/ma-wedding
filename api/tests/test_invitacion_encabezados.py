"""Encabezados de la invitación en `invitacion/vercel.json` (I-10; ADR 0019 y 0030).

- Estático: los encabezados de seguridad y `noindex` están, la caché de imágenes no cambió y no
  se usa ninguna función propietaria de Vercel (rewrites, functions, crons, middleware…).
- Con E2E=1: un servidor local aplica EXACTAMENTE esas reglas a `invitacion/` y el Chrome
  instalado abre la invitación: cero violaciones de CSP y cero errores de JavaScript (la CSP del
  encabezado se suma a la del <meta> de index.html; el navegador aplica las dos).
"""

import http.server
import json
import os
import re
import threading
from functools import partial
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
INVITACION = REPO / "invitacion"
CONFIG = json.loads((INVITACION / "vercel.json").read_text(encoding="utf-8"))
ESPERADOS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Robots-Tag": "noindex, nofollow",
}


def _regex(fuente: str) -> re.Pattern[str]:
    """Las fuentes de vercel.json usadas aquí son regex con grupos (path-to-regexp)."""
    return re.compile("^" + fuente + "$")


def encabezados_para(ruta: str) -> dict[str, str]:
    salida: dict[str, str] = {}
    for regla in CONFIG["headers"]:
        if _regex(regla["source"]).match(ruta):
            salida |= {h["key"]: h["value"] for h in regla["headers"]}
    return salida


def test_solo_cleanurls_y_encabezados() -> None:
    assert set(CONFIG) == {"cleanUrls", "headers"} and CONFIG["cleanUrls"] is True


def test_encabezados_de_seguridad_en_toda_ruta() -> None:
    for ruta in ("/", "/index.html", "/og.jpg", "/mono.webp", "/orn-anillo.svg"):
        assert ESPERADOS.items() <= encabezados_para(ruta).items(), ruta


def test_la_cache_de_imagenes_no_cambio() -> None:
    assert encabezados_para("/mono.webp")["Cache-Control"] == "public, max-age=86400"
    assert "Cache-Control" not in encabezados_para("/")


# ------------------------------------------------------------------------- navegador (E2E=1)
class _Estatico(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        ruta = self.path.split("?", 1)[0].split("#", 1)[0]
        for k, v in encabezados_para(ruta).items():
            self.send_header(k, v)
        super().end_headers()

    def log_message(self, *args: object) -> None:
        pass


@pytest.mark.skipif(not os.environ.get("E2E"), reason="solo con E2E=1 (check --e2e)")
def test_la_invitacion_funciona_con_los_encabezados() -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    srv = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(_Estatico, directory=str(INVITACION))
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://localhost:{srv.server_port}"
    csp: list[str] = []
    errores: list[str] = []
    try:
        with sync_api.sync_playwright() as p:
            for canal in ("chrome", "msedge"):
                try:
                    b = p.chromium.launch(channel=canal, headless=True)
                    break
                except Exception:  # noqa: BLE001, S112
                    continue
            else:
                pytest.fail("No se encontró Chrome ni Edge instalados")
            for ancho in (390, 1440):
                ctx = b.new_context(viewport={"width": ancho, "height": 900}, locale="es-MX")
                ctx.expose_function("__csp", lambda v: csp.append(v))
                ctx.add_init_script(
                    "document.addEventListener('securitypolicyviolation', e => "
                    "window.__csp(e.violatedDirective + ' ' + (e.blockedURI || '')))"
                )
                page = ctx.new_page()
                page.on("pageerror", lambda e: errores.append(str(e)))
                r = page.goto(base + "/", wait_until="networkidle")
                # Playwright entrega los nombres de encabezado en minúsculas.
                assert {k: r.headers.get(k.lower()) for k in ESPERADOS} == ESPERADOS
                assert page.locator("text=Mayra").first.is_visible()
                assert page.title()
                ancho_doc = page.evaluate("document.documentElement.scrollWidth")
                assert ancho_doc <= ancho  # sin scroll horizontal
                ctx.close()
            b.close()
    finally:
        srv.shutdown()
    assert csp == [], csp
    assert errores == [], errores
