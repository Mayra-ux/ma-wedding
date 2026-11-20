"""Aplicación FastAPI: salud, API pública de la invitación (I-4) y autenticación del panel (I-6).

- `/health`: sin DB.
- `/api/v1/public/...`: sub-aplicación con CORS restringido, límites y tamaño de cuerpo.
- `/api/v1/auth/...` y `/api/v1/admin/...`: panel, mismo origen, sin CORS (app/panel.py).
- `/admin/`: página provisional del panel hasta I-9.
- Todas las respuestas llevan los encabezados de seguridad y `X-Request-ID`; el log de
  acceso usa una lista cerrada de campos (app/seguridad.py).
"""

import logging
from datetime import timedelta

from fastapi import FastAPI, Response
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.errores import AtrapaErrores, instalar_manejadores
from app.estado import Reloj, reloj_sistema
from app.google import GoogleReal, ProveedorGoogle
from app.limites import LimitadorVentana
from app.panel import ContextoPanel, crear_app_admin, crear_app_auth, crear_panel_provisional
from app.publica import ContextoPublico, crear_app_publica
from app.seguridad import SeguridadYAcceso
from app.sesiones_panel import Duraciones, Listas, LlavesPanel, SecretoInvalido
from app.tokens import Llaves, LlavesNoConfiguradas

log = logging.getLogger("app")


def _llaves_o_nada(settings: Settings) -> Llaves | None:
    try:
        return settings.llaves()
    except LlavesNoConfiguradas:
        log.warning("llaves de tokens no configuradas: la API pública responderá 500")
        return None


def _sesiones_o_nada(settings: Settings) -> sessionmaker[Session] | None:
    if not settings.database_url:
        return None
    from app.db import make_engine, make_sessionmaker

    return make_sessionmaker(make_engine(settings.database_url))


def _marcador(valor: str | None) -> bool:
    """Vacío o marcador de .env.example (__GENERAR__, __CAMBIAR__…): no configurado."""
    return not valor or any(m in valor for m in ("__GENERAR__", "__CAMBIAR__"))


def _llaves_panel(settings: Settings) -> LlavesPanel | None:
    if settings.session_secret is None or _marcador(settings.session_secret.get_secret_value()):
        return None
    try:
        return LlavesPanel.desde_secreto(settings.session_secret.get_secret_value())
    except SecretoInvalido as exc:
        raise RuntimeError(str(exc)) from None  # el mensaje no incluye el valor


def _google(settings: Settings) -> ProveedorGoogle | None:
    secreto = settings.google_client_secret
    if (
        _marcador(settings.google_client_id)
        or secreto is None
        or _marcador(secreto.get_secret_value())
    ):
        return None
    return GoogleReal(settings.google_client_id, settings.google_client_secret.get_secret_value())


def create_app(
    settings: Settings | None = None,
    *,
    sesiones: sessionmaker[Session] | None = None,
    llaves: Llaves | None = None,
    reloj: Reloj = reloj_sistema,
    google: ProveedorGoogle | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    # Sin documentación interactiva pública: la API no expone su esquema.
    app = FastAPI(title="M&A RSVP API", docs_url=None, redoc_url=None, openapi_url=None)
    instalar_manejadores(app)

    @app.get("/health", include_in_schema=False)
    def health(response: Response) -> dict[str, str]:
        response.headers["Cache-Control"] = "no-store"
        return {"status": "ok"}

    sesiones = sesiones if sesiones is not None else _sesiones_o_nada(settings)
    ctx = ContextoPublico(
        sesiones=sesiones,
        llaves=llaves if llaves is not None else _llaves_o_nada(settings),
        reloj=reloj,
        limite_consulta=LimitadorVentana(settings.rate_limit_token_lookup_per_hour),
        limite_respuesta=LimitadorVentana(settings.rate_limit_token_response_per_hour),
        limite_ip=LimitadorVentana(settings.rate_limit_ip_per_hour),
    )
    app.state.publico = ctx
    app.mount(
        "/api/v1/public",
        crear_app_publica(ctx, settings.invitation_origin, settings.max_body_public),
    )

    panel = ContextoPanel(
        sesiones=sesiones,
        llaves=_llaves_panel(settings),
        google=google if google is not None else _google(settings),
        client_id=None if _marcador(settings.google_client_id) else settings.google_client_id,
        listas=Listas(novios=settings.correos_novios(), planner=settings.correos_planner()),
        duraciones=Duraciones(
            inactividad=timedelta(hours=settings.sesion_inactividad_horas),
            maxima=timedelta(days=settings.sesion_maxima_dias),
        ),
        reloj=reloj,
        panel_origin=settings.panel_origin,
        limite_ip=LimitadorVentana(settings.rate_limit_ip_per_hour),
    )
    if not panel.configurado:
        log.warning("login del panel no configurado: /api/v1/auth responderá 503")
    app.state.panel = panel
    app.state.admin = crear_app_admin(panel, settings.max_body_admin)
    app.mount("/api/v1/auth", crear_app_auth(panel, settings.max_body_admin))
    app.mount("/api/v1/admin", app.state.admin)
    app.mount("/admin", crear_panel_provisional())

    app.add_middleware(AtrapaErrores)
    app.add_middleware(SeguridadYAcceso, hsts=settings.security_hsts)
    return app


app = create_app()
