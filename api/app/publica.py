"""API pública de la invitación (fase I-4; contrato 07 §7.1, ADR 0007, 0013, 0016, 0017, 0019).

Se monta en /api/v1/public como sub-aplicación con su propio CORS (solo el origen de la
invitación), límite por IP y tamaño máximo de cuerpo. El token siempre llega en el cuerpo.

Orden de las comprobaciones (lo que no depende del token se responde antes de buscarlo,
así ningún error revela si un token existe):
  1. límite por IP (429) · 2. cuerpo > 4 KB (413) · 3. JSON/tipos/campos (400)
  4. longitudes y caracteres (422 validacion) · 5. límite por token (429)
  6. token no válido por cualquier motivo (404 idéntico) · 7. plazo (409) · 8. rango (422)
"""

import hashlib
import hmac
from dataclasses import dataclass

from fastapi import FastAPI, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.cors import CORSMiddleware

from app.enlaces import EnlaceNoValido, buscar_por_token
from app.errores import AtrapaErrores, ErrorAPI, instalar_manejadores
from app.esquemas import (
    MAX_ALERGIAS,
    MAX_MENSAJE,
    ConsultaPublica,
    EntradaConsulta,
    EntradaRespuesta,
    RespuestaGuardada,
    RespuestaPublica,
    normalizar_texto,
)
from app.estado import Estado, Reloj, calcular_estado, fecha_limite_mostrar, iso_mx
from app.limites import LimitadorVentana, LimiteDeCuerpo, LimitePorIP
from app.models import ConfiguracionEvento, Invitacion, VersionRespuesta
from app.respuestas import registrar_respuesta
from app.tokens import Llaves, parsear_token


@dataclass
class ContextoPublico:
    sesiones: sessionmaker[Session] | None
    llaves: Llaves | None
    reloj: Reloj
    limite_consulta: LimitadorVentana  # por token
    limite_respuesta: LimitadorVentana  # por token
    limite_ip: LimitadorVentana


# --------------------------------------------------------------------------- utilidades
def _requeridos(ctx: ContextoPublico) -> tuple[sessionmaker[Session], Llaves]:
    if ctx.sesiones is None or ctx.llaves is None:
        raise RuntimeError("API pública sin DATABASE_URL o sin llaves de tokens")
    return ctx.sesiones, ctx.llaves


def _clave_token(llaves: Llaves, token: str) -> tuple[str, bytes]:
    """Clave del límite por token: su HMAC. El token nunca queda como clave en memoria."""
    raw = parsear_token(token)
    if raw is not None:
        return ("token", hmac.new(llaves.hash_actual, raw, hashlib.sha256).digest())
    # Formato inválido: también se limita (no revela nada), con otro dominio de HMAC.
    datos = b"invalido|" + token.encode("utf-8", "replace")[:256]
    return ("token", hmac.new(llaves.hash_actual, datos, hashlib.sha256).digest())


def _limitar_token(limitador: LimitadorVentana, llaves: Llaves, token: str) -> None:
    permitido, reintentar = limitador.permitir(_clave_token(llaves, token))
    if not permitido:
        raise ErrorAPI(429, "demasiadas_solicitudes", headers={"retry-after": str(reintentar)})


def _buscar(s: Session, token: str, llaves: Llaves, request: Request, bloquear: bool) -> Invitacion:
    try:
        inv = buscar_por_token(s, token, llaves, bloquear=bloquear)
    except EnlaceNoValido:
        raise ErrorAPI(404, "enlace_no_valido") from None
    request.state.codigo_inv = inv.codigo  # el log de acceso puede incluir el código INV
    return inv


def _vigente(s: Session, invitacion_id: int) -> VersionRespuesta | None:
    return s.scalar(
        select(VersionRespuesta).where(
            VersionRespuesta.invitacion_id == invitacion_id, VersionRespuesta.vigente
        )
    )


def _respuesta_publica(v: VersionRespuesta | None) -> RespuestaPublica | None:
    if v is None:
        return None
    return RespuestaPublica(
        asiste=v.asiste,
        confirmados=v.confirmados,
        alergias=v.alergias,
        mensaje=v.mensaje,
        actualizada=iso_mx(v.creada_en),
    )


def _validar_textos(entrada: EntradaRespuesta) -> tuple[str | None, str | None]:
    campos: dict[str, str] = {}
    resultado: dict[str, str | None] = {}
    for campo, valor, maximo in (
        ("alergias", entrada.alergias, MAX_ALERGIAS),
        ("mensaje", entrada.mensaje, MAX_MENSAJE),
    ):
        try:
            resultado[campo] = normalizar_texto(valor, campo, maximo)
        except ErrorAPI as exc:
            campos.update(exc.fields or {})
    if campos:
        raise ErrorAPI(422, "validacion", campos)
    return resultado["alergias"], resultado["mensaje"]


# --------------------------------------------------------------------------- aplicación
def crear_app_publica(ctx: ContextoPublico, origen_invitacion: str, max_cuerpo: int) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    instalar_manejadores(app)

    @app.post("/invitation/lookup", response_model=ConsultaPublica)
    def consultar(entrada: EntradaConsulta, request: Request) -> ConsultaPublica:
        sesiones, llaves = _requeridos(ctx)
        _limitar_token(ctx.limite_consulta, llaves, entrada.token)
        with sesiones() as s, s.begin():
            inv = _buscar(s, entrada.token, llaves, request, bloquear=False)
            config = s.get(ConfiguracionEvento, 1)
            estado = calcular_estado(
                ctx.reloj(), config.cierre_plazo, config.congelamiento, inv.desbloqueada_hasta
            )
            return ConsultaPublica(
                nombre_mostrar=inv.nombre_mostrar,
                pases=inv.pases,
                fecha_limite=iso_mx(config.cierre_plazo),
                fecha_limite_mostrar=fecha_limite_mostrar(config.cierre_plazo),
                estado=estado.estado.value,
                abierta_hasta=iso_mx(estado.abierta_hasta),
                respuesta=_respuesta_publica(_vigente(s, inv.id)),
            )

    @app.post("/invitation/response", response_model=RespuestaGuardada)
    def responder(entrada: EntradaRespuesta, request: Request) -> RespuestaGuardada:
        alergias, mensaje = _validar_textos(entrada)
        sesiones, llaves = _requeridos(ctx)
        _limitar_token(ctx.limite_respuesta, llaves, entrada.token)
        with sesiones() as s, s.begin():
            # SELECT … FOR UPDATE: plazo, pases y enlace se leen bajo el bloqueo.
            inv = _buscar(s, entrada.token, llaves, request, bloquear=True)
            config = s.get(ConfiguracionEvento, 1, populate_existing=True)
            estado = calcular_estado(
                ctx.reloj(), config.cierre_plazo, config.congelamiento, inv.desbloqueada_hasta
            )
            if estado.estado is not Estado.ABIERTA:
                raise ErrorAPI(409, "plazo_cerrado")
            if entrada.asiste:
                if not 1 <= entrada.confirmados <= inv.pases:
                    raise ErrorAPI(422, "confirmados_fuera_de_rango")
            else:
                if entrada.confirmados != 0:
                    raise ErrorAPI(422, "confirmados_fuera_de_rango")
                alergias = None  # ADR 0017: si no asiste, se vacían las alergias (sin error)
            version = registrar_respuesta(
                s,
                inv.id,
                asiste=entrada.asiste,
                confirmados=entrada.confirmados,
                alergias=alergias,
                mensaje=mensaje,
                origen="invitado",
            )
            s.refresh(version)
            return RespuestaGuardada(respuesta=_respuesta_publica(version))

    # Orden (de fuera hacia dentro): errores → CORS → límite por IP → tamaño de cuerpo → rutas.
    app.add_middleware(LimiteDeCuerpo, max_bytes=max_cuerpo)
    app.add_middleware(LimitePorIP, limitador=ctx.limite_ip)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origen_invitacion],
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
        max_age=600,
    )
    app.add_middleware(AtrapaErrores)
    return app
