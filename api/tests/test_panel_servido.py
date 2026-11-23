"""La API sirve el panel en /admin/ (I-9; ADR 0015, 0029). Sin DB.

- Enrutado por hash: solo existe /admin/ (index.html); no hace falta ninguna reescritura.
- CSP del panel (con Trusted Types) en toda respuesta; index sin caché; /assets/ inmutable.
- El build real (panel/dist, lo genera tools/check.py en el contenedor de Node) no tiene
  scripts ni estilos en línea, ni source maps, ni recursos de terceros.
- Los catálogos del panel coinciden con los de la API.
"""

import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.catalogos import GRUPOS, LADOS, MOTIVOS_REVISION, ROLES_BODA
from app.config import Settings
from app.main import create_app
from app.panel import CACHE_INMUTABLE, PANEL_CSP

REPO = Path(__file__).resolve().parents[2]
DIST = REPO / "panel" / "dist"
INDEX = (
    '<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Panel M&amp;A</title>'
    '<script type="module" crossorigin src="/admin/assets/index-abc123.js"></script></head>'
    '<body><div id="raiz"></div></body></html>'
)


def _cliente(panel_dir: Path | None) -> TestClient:
    return TestClient(create_app(Settings(panel_dir=panel_dir)), raise_server_exceptions=False)


@pytest.fixture
def build(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "errores.css").write_text("body{}", encoding="utf-8")
    return tmp_path


def test_index_con_csp_y_sin_cache(build: Path) -> None:
    r = _cliente(build).get("/admin/")
    assert r.status_code == 200 and r.text == INDEX
    assert r.headers["content-security-policy"] == PANEL_CSP
    assert "require-trusted-types-for 'script'" in PANEL_CSP and "trusted-types 'none'" in PANEL_CSP
    assert "object-src 'none'" in PANEL_CSP and "script-src 'self';" in PANEL_CSP
    assert "unsafe-inline" not in PANEL_CSP and "unsafe-eval" not in PANEL_CSP
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_assets_inmutables_con_csp(build: Path) -> None:
    r = _cliente(build).get("/admin/assets/index-abc123.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == CACHE_INMUTABLE
    assert r.headers["content-security-policy"] == PANEL_CSP
    falta = _cliente(build).get("/admin/assets/no-existe.js")
    assert falta.status_code == 404 and falta.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("ruta", ["/admin/invitaciones", "/admin/inv/INV-001", "/admin/assets/"])
def test_sin_reescrituras_las_rutas_del_panel_van_en_el_hash(build: Path, ruta: str) -> None:
    r = _cliente(build).get(ruta)
    assert r.status_code == 404 and INDEX not in r.text
    # El 404 lo arma la app principal con su CSP base, más estricta que la del panel.
    assert r.headers["content-security-policy"].startswith("default-src 'none'")


def test_admin_sin_diagonal_redirige(build: Path) -> None:
    r = _cliente(build).get("/admin", follow_redirects=False)
    assert r.status_code in (307, 308) and r.headers["location"].endswith("/admin/")


@pytest.mark.parametrize("panel_dir", [None, "vacia"])
def test_sin_build_pagina_503(tmp_path: Path, panel_dir: str | None) -> None:
    r = _cliente(tmp_path if panel_dir else None).get("/admin/")
    assert r.status_code == 503
    assert 'data-codigo="panel_no_compilado"' in r.text
    assert '<link rel="stylesheet" href="/admin/errores.css">' in r.text
    assert r.headers["content-security-policy"] == PANEL_CSP


# --------------------------------------------------------------------------- build real
def _dist() -> Path:
    if not (DIST / "index.html").is_file():
        if os.environ.get("PANEL_DIST_REQUERIDO"):
            pytest.fail("panel/dist no existe: tools/check.py debe compilar el panel antes")
        pytest.skip("panel/dist no compilado (tools/check.py lo compila en el contenedor)")
    return DIST


def test_build_real_compatible_con_la_csp() -> None:
    dist = _dist()
    html = (dist / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.DOTALL)
    assert scripts and all(s.strip() == "" for s in scripts)  # ningún script en línea
    assert re.findall(r'<script type="module" crossorigin src="(/admin/assets/[^"]+\.js)"', html)
    assert "<style" not in html and " style=" not in html and " on" not in html.replace(" only", "")
    assert not list(dist.rglob("*.map"))
    textos = [p.read_text(encoding="utf-8") for p in dist.rglob("*") if p.suffix in (".js", ".css")]
    assert textos
    for t in textos:
        assert "sourceMappingURL" not in t
        assert "fonts.googleapis" not in t and "fonts.gstatic" not in t
    css = next(p for p in (dist / "assets").glob("*.css")).read_text(encoding="utf-8")
    assert "url(/admin/fuentes/cinzel-latin.woff2)" in css
    for f in (
        "mono.webp",
        "errores.css",
        "fuentes/OFL-Cinzel.txt",
        "fuentes/OFL-CormorantGaramond.txt",
    ):
        assert (dist / f).is_file(), f


def test_build_real_servido(tmp_path: Path) -> None:
    dist = _dist()
    c = _cliente(dist)
    html = c.get("/admin/").text
    for ruta in re.findall(r'(?:src|href)="(/admin/[^"]+)"', html):
        r = c.get(ruta)
        assert r.status_code == 200, ruta
        if ruta.startswith("/admin/assets/"):
            assert r.headers["cache-control"] == CACHE_INMUTABLE


def test_mono_identico_al_de_la_invitacion() -> None:
    assert (REPO / "panel" / "public" / "mono.webp").read_bytes() == (
        REPO / "invitacion" / "mono.webp"
    ).read_bytes()


# --------------------------------------------------------------------------- catálogos
def test_catalogos_del_panel_coinciden_con_la_api() -> None:
    js = (REPO / "panel" / "src" / "catalogos.js").read_text(encoding="utf-8")

    def lista(nombre: str) -> tuple[str, ...]:
        cuerpo = re.search(rf"export const {nombre} = \[(.*?)\]", js, re.DOTALL)
        assert cuerpo, nombre
        return tuple(re.findall(r"'([^']*)'", cuerpo.group(1)))

    assert lista("LADOS") == LADOS
    assert lista("GRUPOS") == GRUPOS
    assert lista("ROLES_BODA") == ROLES_BODA
    assert lista("MOTIVOS_REVISION") == MOTIVOS_REVISION
    assert "export const MAX_IMPORTACION = 2 * 1024 * 1024" in js
    assert Settings().max_import_file == 2 * 1024 * 1024
