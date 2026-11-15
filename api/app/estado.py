"""Estado de la sección RSVP para el invitado (ADR 0016) y presentación de fechas.

Función pura con reloj inyectable: los tests simulan cualquier instante.
Fechas en el desfase fijo del centro de México (−06:00), el de CLAUDE.md.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from enum import StrEnum

MX = timezone(timedelta(hours=-6))

Reloj = Callable[[], datetime]


def reloj_sistema() -> datetime:
    return datetime.now(UTC)


class Estado(StrEnum):
    ABIERTA = "abierta"
    CERRADA = "cerrada"
    CONGELADA = "congelada"


@dataclass(frozen=True)
class EstadoRSVP:
    estado: Estado
    abierta_hasta: datetime | None  # cierre del plazo o del desbloqueo vigente


def calcular_estado(
    ahora: datetime,
    cierre_plazo: datetime,
    congelamiento: datetime,
    desbloqueada_hasta: datetime | None,
) -> EstadoRSVP:
    """- Congelada si `ahora ≥ congelamiento` (gana sobre todo).
    - Abierta si `ahora < cierre_plazo`, o con un desbloqueo vigente (`ahora < desbloqueada_hasta`).
    - Cerrada en otro caso. El cierre ocurre exactamente en el instante configurado.
    """
    if ahora.tzinfo is None:
        raise ValueError("el reloj debe dar fechas con zona")
    if ahora >= congelamiento:
        return EstadoRSVP(Estado.CONGELADA, None)
    if ahora < cierre_plazo:
        return EstadoRSVP(Estado.ABIERTA, cierre_plazo)
    if desbloqueada_hasta is not None and ahora < desbloqueada_hasta:
        return EstadoRSVP(Estado.ABIERTA, min(desbloqueada_hasta, congelamiento))
    return EstadoRSVP(Estado.CERRADA, None)


def iso_mx(instante: datetime | None) -> str | None:
    """ISO 8601 con zona −06:00, p. ej. 2027-01-31T00:00:00-06:00."""
    return instante.astimezone(MX).isoformat() if instante is not None else None


def fecha_limite_mostrar(cierre_plazo: datetime) -> date:
    """Último día local para responder: el día del instante anterior al cierre.

    Cierre 2027-01-31T00:00-06:00 → 2027-01-30 («sábado 30 de enero de 2027», ADR 0025).
    """
    return (cierre_plazo.astimezone(MX) - timedelta(microseconds=1)).date()
