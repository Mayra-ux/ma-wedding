"""Aplicación FastAPI: salud y API pública de la invitación (I-4).

- `/health`: sin DB.
- `/api/v1/public/...`: sub-aplicación con CORS restringido, límites y tamaño de cuerpo.
- Todas las respuestas llevan los encabezados de seguridad y `X-Request-ID`; el log de
  acceso usa una lista cerrada de campos (app/seguridad.py).
"""

import logging

from fastapi import FastAPI, Response
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.errores import AtrapaErrores, instalar_manejadores
from app.estado import Reloj, reloj_sistema
from app.limites import LimitadorVentana
from app.publica import ContextoPublico, crear_app_publica
from app.seguridad import SeguridadYAcceso
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


def create_app(
    settings: Settings | None = None,
    *,
    sesiones: sessionmaker[Session] | None = None,
    llaves: Llaves | None = None,
    reloj: Reloj = reloj_sistema,
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

    ctx = ContextoPublico(
        sesiones=sesiones if sesiones is not None else _sesiones_o_nada(settings),
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

    app.add_middleware(AtrapaErrores)
    app.add_middleware(SeguridadYAcceso, hsts=settings.security_hsts)
    return app


app = create_app()
