"""Autenticación del panel con Google simulado (criterios de I-6; ADR 0005, 0015, 0017, 0019).

Todo es ficticio: correos @ejemplo.invalid, llaves generadas en memoria y un Google simulado
que firma id_tokens con una llave RSA propia. Ninguna prueba usa la red.
"""

import logging
import urllib.parse
from dataclasses import dataclass
from datetime import timedelta

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import text
from starlette.routing import Mount

from app.config import Settings
from app.db import make_sessionmaker
from app.google import CodigoRechazado, ProveedorNoDisponible
from app.main import create_app
from app.sesiones_panel import COOKIE_OAUTH, COOKIE_SESION, generar_secreto_sesion
from tests.db.util import llaves_de_prueba
from tests.google_simulado import CLIENT_ID, GoogleSimulado

ORIGEN = "https://testserver"
LOGIN = "/api/v1/auth/google/login"
CALLBACK = "/api/v1/auth/google/callback"
ME = "/api/v1/auth/me"
LOGOUT = "/api/v1/auth/logout"
NOVIA = "novia.ficticia@ejemplo.invalid"
NOVIO = "novio.ficticio@ejemplo.invalid"
PLANNER = "planner.ficticia@ejemplo.invalid"
INTRUSO = "intruso.ficticio@ejemplo.invalid"


# --------------------------------------------------------------------------- rutas de prueba
def agregar_rutas_de_prueba(admin) -> None:  # noqa: ANN001
    """Rutas de ejemplo con la guardia real (en I-6 aún no hay endpoints del panel; I-7 los
    agrega y este mismo test los recorre automáticamente)."""

    def ok() -> dict[str, bool]:
        return {"ok": True}

    def ok_codigo(codigo: str) -> dict[str, str]:
        return {"codigo": codigo}

    admin.add_api_route("/prueba", ok, methods=["GET"])
    admin.add_api_route("/prueba", ok, methods=["POST"])
    admin.add_api_route("/prueba/{codigo}", ok_codigo, methods=["PUT", "PATCH", "DELETE"])
    admin.add_api_route(
        "/exportar-prueba", ok, methods=["POST"], openapi_extra={"permite_planner": True}
    )


def _settings(novios: str, planner: str, secreto: str) -> Settings:
    return Settings(
        panel_origin=ORIGEN,
        google_client_id=CLIENT_ID,
        google_client_secret="secreto-ficticio-de-prueba",  # noqa: S106
        session_secret=secreto,
        admin_emails_novios=novios,
        admin_emails_planner=planner,
    )


def rutas_de_escritura() -> list[tuple[str, str, bool]]:
    """(método, URL, permite_planner) de toda ruta que no es de lectura en auth y admin."""
    app = create_app(_settings(f"{NOVIA},{NOVIO}", PLANNER, generar_secreto_sesion()))
    agregar_rutas_de_prueba(app.state.admin)
    rutas = []
    for montaje in app.routes:
        if not isinstance(montaje, Mount) or montaje.path not in ("/api/v1/auth", "/api/v1/admin"):
            continue
        for ruta in montaje.app.routes:
            if not isinstance(ruta, APIRoute):
                continue
            extra = ruta.openapi_extra or {}
            url = montaje.path + ruta.path.replace("{codigo}", "INV-901")
            for metodo in sorted(ruta.methods - {"GET", "HEAD", "OPTIONS"}):
                rutas.append((metodo, url, bool(extra.get("permite_planner"))))
    return rutas


RUTAS_ESCRITURA = rutas_de_escritura()
RUTAS_ADMIN = [r for r in RUTAS_ESCRITURA if r[1].startswith("/api/v1/admin/")]


# --------------------------------------------------------------------------- fixtures
@dataclass
class Sesion:
    valor: str
    csrf: str

    def cookie(self) -> dict[str, str]:
        return {"cookie": f"{COOKIE_SESION}={self.valor}"}

    def escritura(self, **extra: str) -> dict[str, str]:
        return {**self.cookie(), "x-csrf-token": self.csrf, "origin": ORIGEN, **extra}


class Panel:
    def __init__(self, engine, reloj) -> None:  # noqa: ANN001
        self.engine, self.reloj = engine, reloj
        self.google = GoogleSimulado()
        self.secreto = generar_secreto_sesion()
        self.app = self.fabricar()

    def fabricar(self, novios: str = f"{NOVIA},{NOVIO}", planner: str = PLANNER):  # noqa: ANN201
        app = create_app(
            _settings(novios, planner, self.secreto),
            sesiones=make_sessionmaker(self.engine),
            llaves=llaves_de_prueba(),
            reloj=self.reloj,
            google=self.google,
        )
        agregar_rutas_de_prueba(app.state.admin)
        return app

    def cliente(self, app=None) -> TestClient:  # noqa: ANN001
        return TestClient(app or self.app, base_url=ORIGEN, raise_server_exceptions=False)

    def callback(self, correo: str, cliente: TestClient | None = None, **extra):  # noqa: ANN201
        """Login completo con Google simulado. Devuelve la respuesta del callback."""
        c = cliente or self.cliente()
        r = c.get(LOGIN, follow_redirects=False)
        assert r.status_code == 302, r.text
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(r.headers["location"]).query))
        codigo = "codigo-" + q["state"][:8]
        self.google.preparar(codigo, correo, q["nonce"], **extra)
        return c.get(CALLBACK, params={"code": codigo, "state": q["state"]}, follow_redirects=False)

    def entrar(self, correo: str) -> Sesion:
        r = self.callback(correo)
        assert r.status_code == 302 and r.headers["location"] == "/admin/", r.text
        valor = _cookie(r, COOKIE_SESION).split(";")[0].split("=", 1)[1]
        me = self.cliente().get(ME, headers={"cookie": f"{COOKIE_SESION}={valor}"})
        assert me.status_code == 200, me.text
        return Sesion(valor=valor, csrf=me.json()["csrf_token"])

    def sesiones(self) -> list[tuple]:
        with self.engine.connect() as conn:
            return list(conn.execute(text("SELECT correo, ultima_actividad FROM sesion_admin")))

    def auditoria(self) -> list[tuple]:
        with self.engine.connect() as conn:
            return list(
                conn.execute(text("SELECT actor, accion FROM evento_auditoria ORDER BY id"))
            )


def _cookie(respuesta, nombre: str) -> str:  # noqa: ANN001
    for valor in respuesta.headers.get_list("set-cookie"):
        if valor.startswith(nombre + "="):
            return valor
    raise AssertionError(f"sin Set-Cookie {nombre}")


def _sin_cookie_de_sesion(respuesta) -> bool:  # noqa: ANN001
    return not any(
        v.startswith(COOKIE_SESION + "=") and not v.startswith(COOKIE_SESION + "=;")
        for v in respuesta.headers.get_list("set-cookie")
    )


@pytest.fixture
def panel(app_engine, reloj, limpiar) -> Panel:  # noqa: ANN001
    return Panel(app_engine, reloj)


# --------------------------------------------------------------------------- login
def test_login_novios_crea_sesion_admin(panel: Panel) -> None:
    r = panel.callback(NOVIA)
    assert r.status_code == 302 and r.headers["location"] == "/admin/"
    valor = _cookie(r, COOKIE_SESION).split(";")[0].split("=", 1)[1]
    me = panel.cliente().get(ME, headers={"cookie": f"{COOKIE_SESION}={valor}"})
    assert me.status_code == 200
    assert me.json()["correo"] == NOVIA and me.json()["rol"] == "admin"
    assert len(me.json()["csrf_token"]) >= 43
    # La DB guarda solo el HMAC del identificador (32 bytes), nunca el valor de la cookie.
    with panel.engine.connect() as conn:
        hashes = conn.execute(text("SELECT hash_sesion FROM sesion_admin")).scalars().all()
    assert len(hashes) == 1 and len(hashes[0]) == 32
    assert valor.encode() not in hashes[0]
    assert panel.auditoria() == [(NOVIA, "login")]
    # El canje usó PKCE y la URI de redirección registrada.
    _codigo, verificador, redirect_uri = panel.google.canjes[-1]
    assert redirect_uri == ORIGEN + CALLBACK and 43 <= len(verificador) <= 128


def test_login_planner_es_lector(panel: Panel) -> None:
    s = panel.entrar(PLANNER)
    assert panel.cliente().get(ME, headers=s.cookie()).json()["rol"] == "lector"


def test_correo_en_mayusculas_se_normaliza(panel: Panel) -> None:
    s = panel.entrar(NOVIO.upper())
    assert panel.cliente().get(ME, headers=s.cookie()).json()["correo"] == NOVIO


def test_correo_fuera_de_lista_403_sin_sesion(panel: Panel, caplog) -> None:  # noqa: ANN001
    caplog.set_level(logging.DEBUG)
    r = panel.callback(INTRUSO)
    assert r.status_code == 403
    assert 'data-codigo="correo_no_autorizado"' in r.text
    assert _sin_cookie_de_sesion(r)
    assert panel.sesiones() == []
    assert panel.auditoria() == []  # el correo de un tercero no se guarda
    assert INTRUSO not in r.text and INTRUSO not in caplog.text
    assert "login_denegado motivo=correo_no_autorizado" in caplog.text


@pytest.mark.parametrize(
    ("caso", "extra"),
    [
        ("correo no verificado", {"email_verified": False}),
        ("sin email_verified", {"email_verified": ...}),
        ("audiencia ajena", {"aud": "otro.apps.googleusercontent.com"}),
        ("emisor ajeno", {"iss": "https://evil.ejemplo.invalid"}),
        ("vencido", {"exp": 1_000_000_000, "iat": 999_990_000}),
        ("nonce distinto", {"nonce": "otro"}),
    ],
)
def test_identidad_no_verificada_403_sin_sesion(panel: Panel, caso: str, extra: dict) -> None:
    if "nonce" in extra:
        # El nonce lo fija el simulado a partir del login: se sobrescribe después.
        c = panel.cliente()
        r = c.get(LOGIN, follow_redirects=False)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(r.headers["location"]).query))
        panel.google.preparar("c-nonce", NOVIA, "otro")
        r = c.get(CALLBACK, params={"code": "c-nonce", "state": q["state"]}, follow_redirects=False)
    else:
        r = panel.callback(NOVIA, **extra)
    assert r.status_code == 403 and 'data-codigo="identidad_no_verificada"' in r.text
    assert _sin_cookie_de_sesion(r) and panel.sesiones() == []


def test_id_token_firmado_con_otra_llave_403(panel: Panel) -> None:
    from tests.google_simulado import llave_rsa

    panel.google.llave_firma = llave_rsa()
    r = panel.callback(NOVIA)
    assert r.status_code == 403 and panel.sesiones() == []


def test_cookie_de_sesion_host_secure_httponly_strict(panel: Panel) -> None:
    r = panel.callback(NOVIA)
    partes = [p.strip() for p in _cookie(r, COOKIE_SESION).split(";")]
    assert partes[0].startswith("__Host-ma_sesion=")
    atributos = {p.split("=")[0].lower(): p for p in partes[1:]}
    assert {"secure", "httponly", "path", "samesite", "max-age"} == set(atributos)
    assert atributos["path"] == "Path=/" and atributos["samesite"] == "SameSite=Strict"
    assert atributos["max-age"] == f"Max-Age={7 * 24 * 3600}"
    assert "domain" not in atributos  # prefijo __Host-: sin Domain
    # La cookie temporal de OAuth se borra al volver de Google (un solo uso).
    assert _cookie(r, COOKIE_OAUTH).startswith(f"{COOKIE_OAUTH}=; Max-Age=0;")


def test_cookie_temporal_oauth_lax(panel: Panel) -> None:
    r = panel.cliente().get(LOGIN, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    partes = [p.strip() for p in _cookie(r, COOKIE_OAUTH).split(";")]
    assert set(partes[1:]) == {"Max-Age=600", "Path=/", "Secure", "HttpOnly", "SameSite=Lax"}


# --------------------------------------------------------------------------- state y código
def _login(panel: Panel):  # noqa: ANN202
    c = panel.cliente()
    r = c.get(LOGIN, follow_redirects=False)
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(r.headers["location"]).query))
    panel.google.preparar("c1", NOVIA, q["nonce"])
    return c, q


def test_state_distinto_400(panel: Panel) -> None:
    c, _q = _login(panel)
    r = c.get(CALLBACK, params={"code": "c1", "state": "otro"}, follow_redirects=False)
    assert r.status_code == 400 and 'data-codigo="estado_invalido"' in r.text
    assert panel.google.canjes == []  # ni siquiera se canjea el código
    assert panel.sesiones() == []


def test_sin_cookie_temporal_400(panel: Panel) -> None:
    _c, q = _login(panel)
    r = panel.cliente().get(
        CALLBACK, params={"code": "c1", "state": q["state"]}, follow_redirects=False
    )
    assert r.status_code == 400 and panel.sesiones() == []


def test_cookie_temporal_alterada_400(panel: Panel) -> None:
    c, q = _login(panel)
    valor = c.cookies.get(COOKIE_OAUTH)
    c.cookies.clear()
    r = c.get(
        CALLBACK,
        params={"code": "c1", "state": q["state"]},
        headers={"cookie": f"{COOKIE_OAUTH}={valor[:-3]}abc"},
        follow_redirects=False,
    )
    assert r.status_code == 400 and panel.sesiones() == []


def test_state_reusado_400(panel: Panel) -> None:
    c, q = _login(panel)
    valor = c.cookies.get(COOKIE_OAUTH)
    r = c.get(CALLBACK, params={"code": "c1", "state": q["state"]}, follow_redirects=False)
    assert r.status_code == 302
    # Repetir el callback con la misma cookie temporal: el código ya no sirve en Google.
    panel.google.preparar("c2", NOVIA, q["nonce"])
    r2 = panel.cliente().get(
        CALLBACK,
        params={"code": "c1", "state": q["state"]},
        headers={"cookie": f"{COOKIE_OAUTH}={valor}"},
        follow_redirects=False,
    )
    assert r2.status_code == 400
    assert len(panel.sesiones()) == 1


def test_codigo_rechazado_400_y_google_caido_502(panel: Panel) -> None:
    for falla, status in ((CodigoRechazado, 400), (ProveedorNoDisponible, 502)):
        panel.google.falla = falla
        r = panel.callback(NOVIA)
        assert r.status_code == status and _sin_cookie_de_sesion(r)
    assert panel.sesiones() == []


def test_cancelado_en_google_vuelve_al_panel(panel: Panel) -> None:
    c, q = _login(panel)
    r = c.get(
        CALLBACK, params={"error": "access_denied", "state": q["state"]}, follow_redirects=False
    )
    assert r.status_code == 302 and r.headers["location"] == "/admin/"
    assert panel.sesiones() == []


def test_sin_configuracion_503(app_engine, reloj, limpiar) -> None:  # noqa: ANN001
    app = create_app(
        Settings(panel_origin=ORIGEN), sesiones=make_sessionmaker(app_engine), reloj=reloj
    )
    c = TestClient(app, base_url=ORIGEN, raise_server_exceptions=False)
    assert c.get(LOGIN, follow_redirects=False).status_code == 503
    assert c.get(CALLBACK, params={"code": "x", "state": "y"}).status_code == 503
    assert c.get(ME).status_code == 503


# --------------------------------------------------------------------------- sesión
def test_sin_sesion_401(panel: Panel) -> None:
    c = panel.cliente()
    assert c.get(ME).json()["error"]["code"] == "no_autenticado"
    assert c.get(ME, headers={"cookie": f"{COOKIE_SESION}=inventada"}).status_code == 401
    assert c.get("/api/v1/admin/prueba").status_code == 401
    r = c.post("/api/v1/admin/prueba", headers={"origin": ORIGEN, "x-csrf-token": "x"})
    assert r.status_code == 401


def test_logout_invalida_la_sesion_en_el_servidor(panel: Panel) -> None:
    s = panel.entrar(NOVIA)
    c = panel.cliente()
    r = c.post(LOGOUT, headers=s.escritura())
    assert r.status_code == 204
    assert _cookie(r, COOKIE_SESION).startswith(f"{COOKIE_SESION}=; Max-Age=0;")
    assert panel.sesiones() == []
    # La cookie anterior ya no sirve aunque alguien la conserve.
    assert c.get(ME, headers=s.cookie()).status_code == 401
    assert panel.auditoria() == [(NOVIA, "login"), (NOVIA, "logout")]


def test_logout_sin_csrf_403_y_la_sesion_sigue(panel: Panel) -> None:
    s = panel.entrar(NOVIA)
    c = panel.cliente()
    r = c.post(LOGOUT, headers=s.cookie() | {"origin": ORIGEN})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_invalido"
    assert c.get(ME, headers=s.cookie()).status_code == 200


def test_cierre_por_inactividad(panel: Panel) -> None:
    s = panel.entrar(NOVIA)
    c = panel.cliente()
    panel.reloj.ahora += timedelta(hours=7, minutes=59)
    assert c.get(ME, headers=s.cookie()).status_code == 200  # renueva la actividad
    panel.reloj.ahora += timedelta(hours=7, minutes=59)
    assert c.get(ME, headers=s.cookie()).status_code == 200
    panel.reloj.ahora += timedelta(hours=8)
    r = c.get(ME, headers=s.cookie())
    assert r.status_code == 401
    assert _cookie(r, COOKIE_SESION).startswith(f"{COOKIE_SESION}=; Max-Age=0;")
    assert panel.sesiones() == []


def test_actividad_se_escribe_como_mucho_cada_5_minutos(panel: Panel) -> None:
    s = panel.entrar(NOVIA)
    c = panel.cliente()
    inicial = panel.sesiones()[0][1]
    panel.reloj.ahora += timedelta(minutes=4)
    c.get(ME, headers=s.cookie())
    assert panel.sesiones()[0][1] == inicial
    panel.reloj.ahora += timedelta(minutes=2)
    c.get(ME, headers=s.cookie())
    assert panel.sesiones()[0][1] == panel.reloj.ahora


def test_duracion_maxima_7_dias(panel: Panel) -> None:
    s = panel.entrar(NOVIA)
    c = panel.cliente()
    for _ in range(23):  # 23 × 7 h = 161 h < 168 h, siempre activa
        panel.reloj.ahora += timedelta(hours=7)
        assert c.get(ME, headers=s.cookie()).status_code == 200
    panel.reloj.ahora += timedelta(hours=7)  # 168 h
    assert c.get(ME, headers=s.cookie()).status_code == 401
    assert panel.sesiones() == []


def test_quitar_correo_de_la_lista_y_reiniciar_corta_la_sesion(panel: Panel) -> None:
    s_novia = panel.entrar(NOVIA)
    s_novio = panel.entrar(NOVIO)
    # "Reinicio": nueva app con las listas cambiadas, misma DB y mismo SESSION_SECRET.
    reiniciada = panel.cliente(panel.fabricar(novios=NOVIO, planner=PLANNER))
    r = reiniciada.get(ME, headers=s_novia.cookie())
    assert r.status_code == 401
    assert [f[0] for f in panel.sesiones()] == [NOVIO]  # la sesión de la novia se borró
    assert reiniciada.get(ME, headers=s_novio.cookie()).status_code == 200


def test_mover_correo_a_planner_cambia_el_rol(panel: Panel) -> None:
    s = panel.entrar(NOVIO)
    reiniciada = panel.cliente(panel.fabricar(novios=NOVIA, planner=f"{PLANNER},{NOVIO}"))
    assert reiniciada.get(ME, headers=s.cookie()).json()["rol"] == "lector"
    r = reiniciada.post("/api/v1/admin/prueba", headers=s.escritura())
    assert r.status_code == 403 and r.json()["error"]["code"] == "sin_permiso"


# --------------------------------------------------------------------------- CSRF y permisos
def test_hay_rutas_de_escritura_para_recorrer() -> None:
    assert ("POST", LOGOUT, False) in RUTAS_ESCRITURA
    assert len(RUTAS_ADMIN) >= 5


@pytest.mark.parametrize(("metodo", "url", "permite_planner"), RUTAS_ESCRITURA)
@pytest.mark.parametrize(
    "caso",
    ["sin encabezado", "token incorrecto", "token de otra sesion", "origin ajeno", "sin origin"],
)
def test_escritura_sin_csrf_valido_403(
    panel: Panel, metodo: str, url: str, permite_planner: bool, caso: str
) -> None:
    s = panel.entrar(NOVIA)
    otra = panel.entrar(NOVIO)
    encabezados = {
        "sin encabezado": s.cookie() | {"origin": ORIGEN},
        "token incorrecto": s.escritura(**{"x-csrf-token": "A" * 43}),
        "token de otra sesion": s.escritura(**{"x-csrf-token": otra.csrf}),
        "origin ajeno": s.escritura(origin="https://evil.ejemplo.invalid"),
        "sin origin": {k: v for k, v in s.escritura().items() if k != "origin"},
    }[caso]
    r = panel.cliente().request(metodo, url, headers=encabezados)
    assert r.status_code == 403, (caso, r.status_code, r.text)
    assert r.json()["error"]["code"] == "csrf_invalido"


@pytest.mark.parametrize(("metodo", "url", "permite_planner"), RUTAS_ADMIN)
def test_planner_403_en_cada_escritura(
    panel: Panel, metodo: str, url: str, permite_planner: bool
) -> None:
    planner = panel.entrar(PLANNER)
    novia = panel.entrar(NOVIA)
    c = panel.cliente()
    r = c.request(metodo, url, headers=planner.escritura())
    if permite_planner:
        # La guardia la deja pasar (la ruta puede responder 404/409/422 por los datos).
        assert r.status_code != 403, r.text
    else:
        assert r.status_code == 403 and r.json()["error"]["code"] == "sin_permiso"
    # Los novios nunca reciben 403 de la guardia (I-7: las rutas reales dan 404 sin datos).
    assert c.request(metodo, url, headers=novia.escritura()).status_code != 403


def test_planner_puede_leer(panel: Panel) -> None:
    s = panel.entrar(PLANNER)
    assert panel.cliente().get("/api/v1/admin/prueba", headers=s.cookie()).status_code == 200


def test_cuerpo_del_panel_maximo_64_kb(panel: Panel) -> None:
    s = panel.entrar(NOVIA)
    r = panel.cliente().post(
        "/api/v1/admin/prueba",
        headers=s.escritura(**{"content-type": "application/json"}),
        content=b"x" * (64 * 1024 + 1),
    )
    assert r.status_code == 413


# --------------------------------------------------------------------------- encabezados y logs
@pytest.mark.parametrize("ruta", [ME, LOGIN, CALLBACK, "/api/v1/admin/prueba", "/admin/"])
def test_encabezados_de_seguridad(panel: Panel, ruta: str) -> None:
    r = panel.cliente().get(ruta, follow_redirects=False)
    h = r.headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "no-referrer"
    assert h["cache-control"] == "no-store"
    assert h["x-request-id"]
    assert "server" not in h
    assert "access-control-allow-origin" not in h  # el panel no tiene CORS
    csp = h["content-security-policy"]
    assert "frame-ancestors 'none'" in csp and "base-uri 'none'" in csp
    if ruta in ("/admin/", CALLBACK):
        assert csp == (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )


def test_panel_provisional_sin_scripts_en_linea(panel: Panel) -> None:
    html = panel.cliente().get("/admin/").text
    assert '<script src="panel.js" defer></script>' in html
    assert "<script>" not in html and " style=" not in html and "onclick" not in html
    js = panel.cliente().get("/admin/panel.js").text
    assert "innerHTML" not in js and "textContent" in js


def test_logs_sin_correo_codigo_token_ni_secretos(panel: Panel, caplog) -> None:  # noqa: ANN001
    caplog.set_level(logging.DEBUG)
    s = panel.entrar(NOVIA)
    panel.cliente().post(LOGOUT, headers=s.escritura())
    panel.callback(INTRUSO)
    codigos = [c for c, _v, _u in panel.google.canjes]
    prohibidos = [NOVIA, INTRUSO, s.valor, s.csrf, *codigos]
    # Solo los logs del servidor: el cliente de pruebas (httpx2) registra la URL que él pide.
    servidor = " | ".join(r.getMessage() for r in caplog.records if not r.name.startswith("httpx"))
    assert "login_ok rol=admin" in servidor  # se capturó el log del servidor
    for valor in prohibidos:
        assert valor not in servidor
    assert "eyJ" not in servidor  # ningún JWT
