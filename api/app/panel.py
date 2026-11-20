"""Autenticación del panel y guardia de /api/v1/admin (I-6; ADR 0005, 0015, 0017, 0019).

Sub-aplicaciones (mismo origen que el panel; sin CORS):
- /api/v1/auth: login y callback de Google, `me` y `logout` (contrato 07 §7.2).
- /api/v1/admin: TODA ruta pasa por `guardia_admin` (dependencia global de la sub-app), así
  que una ruta nueva queda protegida por defecto:
    · sin sesión válida → 401 no_autenticado
    · escritura sin X-CSRF-Token válido o con Origin distinto de PANEL_ORIGIN → 403 csrf_invalido
    · escritura de la planner → 403 sin_permiso, salvo rutas marcadas con
      openapi_extra={"permite_planner": True} (p. ej. la exportación, I-8)
- /admin/: página provisional hasta el panel React de I-9.

Las páginas que ve el navegador al volver de Google (errores del callback) son HTML con
textos fijos: nunca muestran el correo ni valores recibidos.
"""

import hmac
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, sessionmaker
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errores import AtrapaErrores, ErrorAPI, instalar_manejadores
from app.estado import Reloj
from app.google import (
    CodigoRechazado,
    IdentidadNoVerificada,
    ProveedorGoogle,
    ProveedorNoDisponible,
    aleatorio_b64,
    url_autorizacion,
    verificar_id_token,
)
from app.limites import LimitadorVentana, LimiteDeCuerpo, LimitePorIP
from app.sesiones_panel import (
    COOKIE_OAUTH,
    COOKIE_SESION,
    OAUTH_VIGENCIA_S,
    Duraciones,
    EstadoOAuth,
    Listas,
    LlavesPanel,
    Rol,
    Usuario,
    buscar_sesion,
    cerrar_sesion,
    crear_sesion,
    csrf_valido,
    firmar_estado,
    leer_estado,
)
from app.tokens import Llaves

log = logging.getLogger("app.auth")

RUTA_CALLBACK = "/api/v1/auth/google/callback"
METODOS_LECTURA = frozenset({"GET", "HEAD", "OPTIONS"})
PANEL_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)
DIR_PROVISIONAL = Path(__file__).resolve().parent / "panel_provisional"


@dataclass
class ContextoPanel:
    sesiones: sessionmaker[Session] | None
    llaves: LlavesPanel | None
    google: ProveedorGoogle | None
    client_id: str | None
    listas: Listas
    duraciones: Duraciones
    reloj: Reloj
    panel_origin: str
    limite_ip: LimitadorVentana
    llaves_tokens: Llaves | None = None  # enlaces de invitación (I-7)
    invitation_origin: str = "http://localhost:8080"

    @property
    def redirect_uri(self) -> str:
        return self.panel_origin + RUTA_CALLBACK

    @property
    def configurado(self) -> bool:
        return None not in (self.sesiones, self.llaves, self.google, self.client_id)


# --------------------------------------------------------------------------- cookies
def cookie(nombre: str, valor: str, max_age: int, same_site: str) -> str:
    # __Host-: Secure, Path=/ y sin Domain (ADR 0015). HttpOnly: el JS del panel no la lee.
    return f"{nombre}={valor}; Max-Age={max_age}; Path=/; Secure; HttpOnly; SameSite={same_site}"


def borrar_cookie(nombre: str, same_site: str) -> str:
    return cookie(nombre, "", 0, same_site)


# --------------------------------------------------------------------------- páginas HTML
PAGINAS: dict[str, tuple[str, str]] = {
    "estado_invalido": (
        "No se pudo completar el inicio de sesión",
        "La solicitud venció o no es válida. Vuelve a intentarlo desde el panel.",
    ),
    "correo_no_autorizado": (
        "Acceso denegado",
        "Esta cuenta de Google no tiene acceso al panel.",
    ),
    "identidad_no_verificada": (
        "Acceso denegado",
        "No se pudo verificar la cuenta de Google o su correo no está verificado.",
    ),
    "proveedor_no_disponible": (
        "Google no respondió",
        "No se pudo contactar a Google. Inténtalo de nuevo en unos minutos.",
    ),
    "auth_no_configurada": (
        "Inicio de sesión no disponible",
        "El inicio de sesión con Google aún no está configurado en este servidor.",
    ),
}


def pagina_error(status: int, codigo: str) -> HTMLResponse:
    titulo, texto = PAGINAS[codigo]
    html = (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{titulo} · Panel M&amp;A</title><link rel="stylesheet" href="/admin/panel.css">'
        f'</head><body><main data-codigo="{codigo}"><h1>{titulo}</h1><p>{texto}</p>'
        '<p><a href="/admin/">Volver al panel</a></p></main></body></html>'
    )
    r = HTMLResponse(html, status_code=status)
    r.headers["content-security-policy"] = PANEL_CSP
    return r


# --------------------------------------------------------------------------- guardias
def _contexto(request: Request) -> ContextoPanel:
    return request.app.state.panel


def usuario_actual(request: Request) -> Usuario:
    ctx = _contexto(request)
    if ctx.sesiones is None or ctx.llaves is None:
        raise ErrorAPI(503, "auth_no_configurada")
    with ctx.sesiones() as s, s.begin():
        usuario = buscar_sesion(
            s,
            ctx.llaves,
            ctx.listas,
            request.cookies.get(COOKIE_SESION),
            ctx.reloj(),
            ctx.duraciones,
        )
    if usuario is None:
        cabeceras = (
            {"set-cookie": borrar_cookie(COOKIE_SESION, "Strict")}
            if COOKIE_SESION in request.cookies
            else None
        )
        raise ErrorAPI(401, "no_autenticado", headers=cabeceras)
    request.state.usuario = usuario
    return usuario


def exigir_csrf(request: Request, usuario: Usuario) -> None:
    origen = request.headers.get("origin")
    if origen != _contexto(request).panel_origin or not csrf_valido(
        usuario, request.headers.get("x-csrf-token")
    ):
        raise ErrorAPI(403, "csrf_invalido")


UsuarioActual = Annotated[Usuario, Depends(usuario_actual)]


def guardia_admin(request: Request) -> Usuario:
    """Dependencia global de /api/v1/admin: sesión, CSRF en escrituras y rol (ADR 0026).

    - Lectura: novios y planner, salvo rutas `solo_novios` (el enlace en claro).
    - Escritura: solo novios, salvo rutas `permite_planner` (marcar un recordatorio).
    Los novios no tienen congelamiento (ADR 0027); el cierre de la planner lo aplica su ruta.
    """
    usuario = usuario_actual(request)
    ruta = request.scope.get("route")
    extra = getattr(ruta, "openapi_extra", None) or {}
    es_novios = usuario.rol is Rol.ADMIN
    if request.method in METODOS_LECTURA:
        if extra.get("solo_novios") and not es_novios:
            raise ErrorAPI(403, "sin_permiso")
    else:
        exigir_csrf(request, usuario)
        if not es_novios and not extra.get("permite_planner"):
            raise ErrorAPI(403, "sin_permiso")
    return usuario


# --------------------------------------------------------------------------- sub-aplicaciones
def _sub_app(ctx: ContextoPanel, **kwargs: object) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, **kwargs)
    app.state.panel = ctx
    instalar_manejadores(app)
    return app


def _endurecer(
    app: FastAPI, ctx: ContextoPanel, max_cuerpo: int, por_ruta: dict[str, int] | None = None
) -> None:
    # De fuera hacia dentro: errores → límite por IP → tamaño de cuerpo → rutas. Sin CORS.
    app.add_middleware(LimiteDeCuerpo, max_bytes=max_cuerpo, por_ruta=por_ruta)
    app.add_middleware(LimitePorIP, limitador=ctx.limite_ip)
    app.add_middleware(AtrapaErrores)


def crear_app_auth(ctx: ContextoPanel, max_cuerpo: int) -> FastAPI:
    app = _sub_app(ctx)

    @app.get("/google/login")
    def login() -> Response:
        if not ctx.configurado:
            return pagina_error(503, "auth_no_configurada")
        estado = EstadoOAuth(
            state=aleatorio_b64(32),
            nonce=aleatorio_b64(32),
            verificador=aleatorio_b64(48),  # 64 caracteres (RFC 7636: 43–128)
            emitido=int(time.time()),
        )
        destino = url_autorizacion(
            ctx.client_id, ctx.redirect_uri, estado.state, estado.nonce, estado.verificador
        )
        r = RedirectResponse(destino, status_code=302)
        # Lax: la vuelta desde Google es una navegación entre sitios; con Strict no llegaría.
        r.headers.append(
            "set-cookie",
            cookie(COOKIE_OAUTH, firmar_estado(ctx.llaves, estado), OAUTH_VIGENCIA_S, "Lax"),
        )
        return r

    @app.get("/google/callback")
    def callback(
        request: Request,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> Response:
        r = _callback(request, code, state, error)
        r.headers.append("set-cookie", borrar_cookie(COOKIE_OAUTH, "Lax"))  # un solo uso
        return r

    def _callback(
        request: Request, code: str | None, state: str | None, error: str | None
    ) -> Response:
        if not ctx.configurado:
            return pagina_error(503, "auth_no_configurada")
        if error is not None:  # la persona canceló en Google: de vuelta al panel
            return RedirectResponse("/admin/", status_code=302)
        estado = leer_estado(ctx.llaves, request.cookies.get(COOKIE_OAUTH), int(time.time()))
        if (
            estado is None
            or not code
            or not state
            or len(code) > 2048
            or len(state) > 256
            or not _iguales(state, estado.state)
        ):
            log.info("login_denegado motivo=estado_invalido")
            return pagina_error(400, "estado_invalido")
        try:
            id_token = ctx.google.canjear_codigo(code, estado.verificador, ctx.redirect_uri)
            llave = ctx.google.llave_publica(id_token)
            identidad = verificar_id_token(id_token, llave, ctx.client_id, estado.nonce)
        except CodigoRechazado:
            log.info("login_denegado motivo=codigo_rechazado")
            return pagina_error(400, "estado_invalido")
        except ProveedorNoDisponible:
            log.warning("login_fallido motivo=proveedor_no_disponible")
            return pagina_error(502, "proveedor_no_disponible")
        except IdentidadNoVerificada:
            log.info("login_denegado motivo=identidad_no_verificada")
            return pagina_error(403, "identidad_no_verificada")
        rol = ctx.listas.rol(identidad.correo)
        if rol is None:
            # Sin sesión y sin guardar el correo: es un dato personal de un tercero.
            log.info("login_denegado motivo=correo_no_autorizado")
            return pagina_error(403, "correo_no_autorizado")
        with ctx.sesiones() as s, s.begin():
            valor = crear_sesion(s, ctx.llaves, identidad.correo, rol, ctx.reloj(), ctx.duraciones)
        log.info("login_ok rol=%s", rol.value)
        r = RedirectResponse("/admin/", status_code=302)
        max_age = int(ctx.duraciones.maxima.total_seconds())
        r.headers.append("set-cookie", cookie(COOKIE_SESION, valor, max_age, "Strict"))
        return r

    @app.get("/me")
    def me(usuario: UsuarioActual) -> dict[str, str]:
        return {
            "correo": usuario.correo,
            "rol": usuario.rol.value,
            "csrf_token": usuario.csrf_token,
        }

    @app.post("/logout", status_code=204)
    def logout(request: Request, usuario: UsuarioActual) -> Response:
        exigir_csrf(request, usuario)
        with ctx.sesiones() as s, s.begin():
            cerrar_sesion(s, ctx.llaves, request.cookies.get(COOKIE_SESION))
        r = Response(status_code=204)
        r.headers.append("set-cookie", borrar_cookie(COOKIE_SESION, "Strict"))
        return r

    _endurecer(app, ctx, max_cuerpo)
    return app


def _iguales(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8", "replace"), b.encode("utf-8", "replace"))


def crear_app_admin(ctx: ContextoPanel, max_cuerpo: int, max_importacion: int) -> FastAPI:
    """API del panel (I-7, I-8). Todas sus rutas heredan la guardia."""
    from app.panel_rutas import registrar_rutas

    app = _sub_app(ctx, dependencies=[Depends(guardia_admin)])
    registrar_rutas(app)
    importacion = {"/imports/preview": max_importacion, "/imports/apply": max_importacion}
    _endurecer(app, ctx, max_cuerpo, importacion)
    return app


# --------------------------------------------------------------------------- página provisional
class ConEncabezados:
    """Middleware ASGI: fija encabezados (la CSP del panel) en las respuestas que envuelve."""

    def __init__(self, app: ASGIApp, encabezados: dict[str, str]) -> None:
        self.app = app
        self.encabezados = [(k.encode(), v.encode()) for k, v in encabezados.items()]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_con(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                nombres = {k for k, _ in self.encabezados}
                otros = [(k, v) for k, v in mensaje.get("headers", []) if k.lower() not in nombres]
                mensaje = {**mensaje, "headers": [*otros, *self.encabezados]}
            await send(mensaje)

        await self.app(scope, receive, send_con)


def crear_panel_provisional() -> ASGIApp:
    return ConEncabezados(
        StaticFiles(directory=DIR_PROVISIONAL, html=True),
        {"content-security-policy": PANEL_CSP},
    )
