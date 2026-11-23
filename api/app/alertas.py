"""Alertas de las tareas programadas con Healthchecks (I-10; ADR 0019 y 0030).

Por cada ejecución: `/start` al empezar, la URL sola al terminar bien (con el informe de
conteos) y `/fail` si algo falla (con el paso que falló). Healthchecks avisa por correo si llega
un `/fail` o si el aviso no llega a tiempo (la tarea no corrió).

- Sin URL configurada, las alertas están APAGADAS: no se hace ninguna petición.
- El cuerpo nunca lleva datos personales: solo conteos, fechas y el nombre del paso.
- Una alerta que no se puede enviar no cambia el resultado de la tarea: se registra en el log
  (sin la URL, que es secreta) y la tarea sigue.
"""

import logging
import urllib.request
from collections.abc import Callable

log = logging.getLogger("app.alertas")

Abrir = Callable[..., object]
MAX_CUERPO = 10_000  # Healthchecks acepta hasta 100 kB; los informes son cortos


class Alerta:
    def __init__(self, url: str | None, abrir: Abrir = urllib.request.urlopen) -> None:
        self.url = url.rstrip("/") if url else None
        self._abrir = abrir

    @property
    def activa(self) -> bool:
        return self.url is not None

    def _ping(self, sufijo: str, cuerpo: str = "") -> bool:
        if not self.url:
            return False
        datos = cuerpo.encode("utf-8")[:MAX_CUERPO]
        peticion = urllib.request.Request(  # noqa: S310  (URL https validada en config)
            self.url + sufijo,
            data=datos,
            method="POST",
            headers={"Content-Type": "text/plain; charset=utf-8", "User-Agent": "ma-wedding"},
        )
        try:
            respuesta = self._abrir(peticion, timeout=10)
            close = getattr(respuesta, "close", None)
            if close:
                close()
            return True
        except Exception as exc:  # noqa: BLE001  (la alerta nunca tumba la tarea)
            log.warning("no se pudo enviar la alerta %s: %s", sufijo or "/ok", type(exc).__name__)
            return False

    def inicio(self) -> bool:
        return self._ping("/start")

    def exito(self, informe: str) -> bool:
        return self._ping("", informe)

    def fallo(self, paso: str, detalle: str = "") -> bool:
        return self._ping("/fail", f"falló: {paso}" + (f"\n{detalle}" if detalle else ""))
