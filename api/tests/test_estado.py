"""Estado RSVP con reloj simulado y presentación de fechas (sin DB)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.estado import MX, Estado, calcular_estado, fecha_limite_mostrar, iso_mx

CIERRE = datetime(2027, 1, 31, 0, 0, tzinfo=MX)  # 2027-01-31T00:00-06:00 (ADR 0025)
CONGELA = datetime(2027, 2, 6, 0, 0, tzinfo=MX)  # ADR 0027
S = timedelta(seconds=1)


def estado(ahora: datetime, desbloqueo: datetime | None = None):  # noqa: ANN201
    return calcular_estado(ahora, CIERRE, CONGELA, desbloqueo)


def test_cierre_exacto() -> None:
    assert estado(CIERRE - S).estado is Estado.ABIERTA  # un segundo antes: abierta
    assert estado(CIERRE - S).abierta_hasta == CIERRE
    assert estado(CIERRE).estado is Estado.CERRADA  # en el instante: cerrada
    assert estado(CIERRE).abierta_hasta is None


def test_mismo_instante_en_utc() -> None:
    assert estado(datetime(2027, 1, 31, 5, 59, 59, tzinfo=UTC)).estado is Estado.ABIERTA
    assert estado(datetime(2027, 1, 31, 6, 0, 0, tzinfo=UTC)).estado is Estado.CERRADA


def test_desbloqueo_vigente_y_vencido() -> None:
    hasta = CIERRE + timedelta(days=3)
    assert estado(CIERRE + S, hasta).estado is Estado.ABIERTA
    assert estado(CIERRE + S, hasta).abierta_hasta == hasta
    assert estado(hasta - S, hasta).estado is Estado.ABIERTA
    assert estado(hasta, hasta).estado is Estado.CERRADA  # vuelve a cerrada al vencer


def test_desbloqueo_nunca_pasa_del_congelamiento() -> None:
    hasta = CONGELA + timedelta(days=5)  # la API del panel no lo permite; aquí se acota igual
    assert estado(CONGELA - S, hasta).abierta_hasta == CONGELA


def test_congelamiento_exacto_gana_sobre_todo() -> None:
    hasta = CONGELA + timedelta(days=1)
    assert estado(CONGELA - S).estado is Estado.CERRADA
    assert estado(CONGELA).estado is Estado.CONGELADA
    assert estado(CONGELA, hasta).estado is Estado.CONGELADA


def test_reloj_sin_zona_se_rechaza() -> None:
    with pytest.raises(ValueError):
        estado(datetime(2027, 1, 1))  # noqa: DTZ001


def test_fechas_para_mostrar() -> None:
    assert iso_mx(CIERRE) == "2027-01-31T00:00:00-06:00"
    assert iso_mx(datetime(2027, 1, 31, 6, tzinfo=UTC)) == "2027-01-31T00:00:00-06:00"
    assert iso_mx(None) is None
    assert fecha_limite_mostrar(CIERRE) == date(2027, 1, 30)  # «sábado 30 de enero de 2027»
    assert fecha_limite_mostrar(CIERRE).isoformat() == "2027-01-30"
    assert fecha_limite_mostrar(datetime(2027, 1, 31, 0, 0, 1, tzinfo=MX)) == date(2027, 1, 31)
