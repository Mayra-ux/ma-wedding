"""IP del cliente detrás de proxies (I-10; ADR 0030).

Problema: con `FORWARDED_ALLOW_IPS="*"` (lo habitual cuando el proveedor no publica las IPs de
su proxy), uvicorn toma la IP de MÁS A LA IZQUIERDA de `X-Forwarded-For`, que la escribe el
cliente: cualquiera evadiría el límite por IP cambiando ese encabezado.

Solución: se cuenta desde la DERECHA. Cada proxy de confianza agrega al final la IP de quien
le habló; con `TRUSTED_PROXY_HOPS=N`, la IP del cliente es la N-ésima desde la derecha. Lo que
el cliente escriba a la izquierda se ignora. Con N=0 se usa la IP de la conexión. Si el
encabezado trae menos de N entradas (la petición no pasó por todos los proxies), también se
usa la IP de la conexión. uvicorn corre con `--no-proxy-headers` para que no la cambie antes.
"""

import ipaddress

from starlette.types import ASGIApp, Receive, Scope, Send


def ip_del_cliente(conexion: str | None, x_forwarded_for: list[str], saltos: int) -> str | None:
    if saltos <= 0:
        return conexion
    entradas = [e.strip() for valor in x_forwarded_for for e in valor.split(",") if e.strip()]
    if len(entradas) < saltos:
        return conexion
    candidata = entradas[-saltos]
    try:
        return str(ipaddress.ip_address(candidata))
    except ValueError:
        return conexion  # algo que no es una IP: no se confía


class IPDelCliente:
    """Middleware ASGI: fija `scope["client"]` con la IP real antes de los límites."""

    def __init__(self, app: ASGIApp, saltos: int = 0) -> None:
        self.app = app
        self.saltos = saltos

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self.saltos > 0:
            xff = [
                v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"x-forwarded-for"
            ]
            cliente = scope.get("client") or (None, 0)
            ip = ip_del_cliente(cliente[0], xff, self.saltos)
            if ip != cliente[0]:
                scope = {**scope, "client": (ip, 0)}
        await self.app(scope, receive, send)
