"""Límites de abuso de la API pública (ADR 0019): rate limiting en memoria y tamaño de cuerpo.

Se guarda en memoria: basta con una sola instancia (ADR 0019). Las claves por token son su
HMAC (nunca el token); las IPs solo viven aquí y nunca se registran.
"""

import contextlib
import math
import threading
import time
from collections import deque
from collections.abc import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errores import respuesta_error_asgi


class LimitadorVentana:
    """Ventana deslizante: como máximo `limite` eventos por clave en `ventana_s` segundos."""

    def __init__(
        self,
        limite: int,
        ventana_s: float = 3600.0,
        max_claves: int = 50_000,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        if limite < 1:
            raise ValueError("el límite debe ser al menos 1")
        self.limite = limite
        self.ventana_s = ventana_s
        self.max_claves = max_claves
        self._reloj = reloj
        self._eventos: dict[object, deque[float]] = {}
        self._lock = threading.Lock()

    def permitir(self, clave: object) -> tuple[bool, int]:
        """(permitido, segundos para reintentar). Registra el evento si se permite."""
        ahora = self._reloj()
        with self._lock:
            eventos = self._eventos.setdefault(clave, deque())
            while eventos and eventos[0] <= ahora - self.ventana_s:
                eventos.popleft()
            if len(eventos) >= self.limite:
                return False, max(1, math.ceil(eventos[0] + self.ventana_s - ahora))
            eventos.append(ahora)
            if len(self._eventos) > self.max_claves:
                self._podar(ahora)
            return True, 0

    def _podar(self, ahora: float) -> None:
        for clave in [
            c for c, ev in self._eventos.items() if not ev or ev[-1] <= ahora - self.ventana_s
        ]:
            del self._eventos[clave]
        # Si aún sobran (ataque con claves nuevas), se descartan las más antiguas.
        exceso = len(self._eventos) - self.max_claves
        for clave in list(self._eventos)[: max(0, exceso)]:
            del self._eventos[clave]

    def claves(self) -> list[object]:
        with self._lock:
            return list(self._eventos)


class LimitePorIP:
    """Middleware ASGI: rate limiting generoso por IP para todas las rutas que envuelve."""

    def __init__(self, app: ASGIApp, limitador: LimitadorVentana) -> None:
        self.app = app
        self.limitador = limitador

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ip = (scope.get("client") or ("desconocida", 0))[0]
        permitido, reintentar = self.limitador.permitir(("ip", ip))
        if not permitido:
            await respuesta_error_asgi(
                send, 429, "demasiadas_solicitudes", {"retry-after": str(reintentar)}
            )
            return
        await self.app(scope, receive, send)


class _CuerpoDemasiadoGrande(Exception):
    pass


class LimiteDeCuerpo:
    """Middleware ASGI: rechaza cuerpos mayores a `max_bytes` (con o sin Content-Length)."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for nombre, valor in scope.get("headers", []):
            if nombre == b"content-length":
                try:
                    declarado = int(valor)
                except ValueError:
                    await respuesta_error_asgi(send, 400, "solicitud_invalida")
                    return
                if declarado > self.max_bytes:
                    await respuesta_error_asgi(send, 413, "cuerpo_demasiado_grande")
                    return

        recibidos = 0
        excedido = False
        iniciada = False

        async def receive_contado() -> Message:
            nonlocal recibidos, excedido
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                recibidos += len(mensaje.get("body", b""))
                if recibidos > self.max_bytes:
                    excedido = True
                    raise _CuerpoDemasiadoGrande
            return mensaje

        async def send_marcado(mensaje: Message) -> None:
            nonlocal iniciada
            if excedido:  # FastAPI convierte la excepción en un 400; se descarta y se envía 413
                return
            if mensaje["type"] == "http.response.start":
                iniciada = True
            await send(mensaje)

        with contextlib.suppress(_CuerpoDemasiadoGrande):
            await self.app(scope, receive_contado, send_marcado)
        if excedido and not iniciada:
            await respuesta_error_asgi(send, 413, "cuerpo_demasiado_grande")
