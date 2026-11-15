"""Encabezados de seguridad, identificador de petición y log de acceso (ADR 0019, doc 06).

El log usa una lista cerrada de campos: método, ruta sin parámetros, estado, duración,
id de petición y código INV cuando aplica. Nunca cuerpos, tokens, nombres ni IPs.
Reemplaza al access log de uvicorn (que registra IP y cadena de consulta).
"""

import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

log_acceso = logging.getLogger("app.acceso")

ENCABEZADOS_BASE: dict[str, str] = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
}
HSTS = "max-age=31536000; includeSubDomains"


class SeguridadYAcceso:
    def __init__(self, app: ASGIApp, hsts: bool = False) -> None:
        self.app = app
        self.encabezados = dict(ENCABEZADOS_BASE)
        if hsts:  # solo con el dominio definitivo (SECURITY_HSTS, ADR 0019/0021)
            self.encabezados["strict-transport-security"] = HSTS

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        inicio = time.perf_counter()
        estado = 500

        async def send_con_encabezados(mensaje: Message) -> None:
            nonlocal estado
            if mensaje["type"] == "http.response.start":
                estado = mensaje["status"]
                existentes = {k.lower() for k, _ in mensaje.get("headers", [])}
                extra = [
                    (k.encode(), v.encode())
                    for k, v in self.encabezados.items()
                    if k.encode() not in existentes
                ]
                extra.append((b"x-request-id", request_id.encode()))
                mensaje = {**mensaje, "headers": [*mensaje.get("headers", []), *extra]}
            await send(mensaje)

        try:
            await self.app(scope, receive, send_con_encabezados)
        finally:
            duracion_ms = (time.perf_counter() - inicio) * 1000
            inv = scope.get("state", {}).get("codigo_inv")
            log_acceso.info(
                "metodo=%s ruta=%s estado=%s duracion_ms=%.1f request_id=%s%s",
                scope.get("method"),
                scope.get("path"),
                estado,
                duracion_ms,
                request_id,
                f" inv={inv}" if inv else "",
            )
