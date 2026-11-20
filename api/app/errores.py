"""Errores de la API con la forma común del contrato 07.

{"error": {"code": "<codigo>", "message": "<texto>", "fields": {...}}}

- Ningún error incluye valores de entrada, tokens, datos personales ni trazas (ADR 0019).
- Los mensajes son PROVISIONALES hasta aprobar los textos de la invitación en I-5.
"""

import json
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("app.errores")

# Mensajes provisionales (I-4); los textos visibles se aprueban en I-5.
MENSAJES: dict[str, str] = {
    "solicitud_invalida": "La solicitud no es válida.",
    "enlace_no_valido": "Este enlace no es válido.",
    "plazo_cerrado": "El plazo para confirmar ya cerró.",
    "confirmados_fuera_de_rango": "El número de asistentes no es válido.",
    "validacion": "Revisa los datos enviados.",
    "cuerpo_demasiado_grande": "La solicitud es demasiado grande.",
    "demasiadas_solicitudes": "Demasiados intentos. Intenta de nuevo más tarde.",
    "no_encontrado": "No encontrado.",
    "metodo_no_permitido": "Método no permitido.",
    "error_interno": "Ocurrió un error. Intenta de nuevo.",
    # Panel (I-6)
    "no_autenticado": "Inicia sesión para continuar.",
    "sin_permiso": "No tienes permiso para esta acción.",
    "csrf_invalido": "La solicitud no es válida. Recarga el panel e inténtalo de nuevo.",
    "auth_no_configurada": "El inicio de sesión no está configurado.",
    # API del panel (I-7)
    "pases_menores_que_confirmados": "Ajusta la respuesta antes de bajar los pases.",
    "ya_archivada": "La invitación ya está archivada.",
    "no_archivada": "La invitación no está archivada.",
    "archivada": "La invitación está archivada; restáurala primero.",
    "plazo_aun_abierto": "El plazo sigue abierto; aún no se puede desbloquear.",
    "mas_alla_del_congelamiento": "El desbloqueo no puede pasar del congelamiento.",
    "rsvp_congelado": "La confirmación de los invitados ya está congelada.",
    "sin_enlace_activo": "La invitación no tiene enlace activo.",
    "requiere_revision": "Corrige la invitación antes de generar el enlace.",
    "ya_tiene_enlace": "La invitación ya tiene un enlace activo.",
    "recordatorios_cerrados": "El periodo de recordatorios terminó.",
    "sin_telefono": "La invitación no tiene ese teléfono.",
    "conflicto_codigo": "No se pudo asignar el código. Inténtalo de nuevo.",
    # Importación y exportación (I-8)
    "formato_no_soportado": "Solo se aceptan archivos .xlsx o .csv.",
    "archivo_no_valido": "El archivo no es válido o está dañado.",
    "columnas_faltantes": "Al archivo le faltan columnas de la planner.",
    "hoja_requerida": "Elige la hoja que quieres importar.",
    "hoja_no_encontrada": "No se encontró esa hoja de invitados en el archivo.",
    "archivo_con_errores": "El archivo tiene filas con errores; no se aplicó nada.",
}


class ErrorAPI(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        fields: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code)
        self.status, self.code, self.fields, self.headers = status, code, fields, headers


def cuerpo_error(code: str, fields: dict[str, str] | None = None) -> dict:
    error: dict = {"code": code, "message": MENSAJES[code]}
    if fields:
        error["fields"] = fields
    return {"error": error}


def respuesta_error(
    status: int,
    code: str,
    fields: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(cuerpo_error(code, fields), status_code=status, headers=headers)


async def respuesta_error_asgi(
    send: Send, status: int, code: str, headers: dict[str, str] | None = None
) -> None:
    cuerpo = json.dumps(cuerpo_error(code), ensure_ascii=False).encode("utf-8")
    cabeceras = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(cuerpo)).encode()),
    ] + [(k.encode(), v.encode()) for k, v in (headers or {}).items()]
    await send({"type": "http.response.start", "status": status, "headers": cabeceras})
    await send({"type": "http.response.body", "body": cuerpo})


def instalar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorAPI)
    async def _error_api(request: Request, exc: ErrorAPI) -> JSONResponse:
        return respuesta_error(exc.status, exc.code, exc.fields, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
        # JSON inválido, tipos incorrectos, faltantes o campos de más. Nunca se repite la entrada.
        return respuesta_error(400, "solicitud_invalida")

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "no_encontrado", 405: "metodo_no_permitido"}.get(exc.status_code)
        if code is None:
            return respuesta_error(
                400 if exc.status_code < 500 else 500,
                "solicitud_invalida" if exc.status_code < 500 else "error_interno",
            )
        return respuesta_error(exc.status_code, code)


class AtrapaErrores:
    """Middleware ASGI: cualquier excepción no prevista → 500 `error_interno`.

    Solo registra el tipo de la excepción (nunca su mensaje, que podría llevar datos) y no
    la vuelve a lanzar, para que el servidor no imprima la traza.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        iniciada = False

        async def send_marcado(mensaje: Message) -> None:
            nonlocal iniciada
            if mensaje["type"] == "http.response.start":
                iniciada = True
            await send(mensaje)

        try:
            await self.app(scope, receive, send_marcado)
        except Exception as exc:  # noqa: BLE001
            request_id = scope.get("state", {}).get("request_id", "-")
            log.error("error_interno tipo=%s request_id=%s", type(exc).__name__, request_id)
            if not iniciada:
                await respuesta_error_asgi(send, 500, "error_interno")
