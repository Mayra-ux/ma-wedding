"""Borrado programado (I-10; ADR 0010; reglas F5, F6 y F10) con el usuario de EJECUCIÓN.

Datos ficticios. Las corridas son repetibles: la segunda ejecución del mismo día no cambia nada.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.estado import MX
from app.purga import contar_tablas, purgar
from tests.db.util import nueva_invitacion, nueva_version

TEL = "+" + "52" + "2025550123"  # serie 555-01XX, ficticia
TEL2 = "+" + "52" + "2025550124"
BORRADO_1 = datetime(2027, 4, 5, 0, 0, tzinfo=MX)
BORRADO_2 = datetime(2027, 6, 4, 0, 0, tzinfo=MX)
S = timedelta(seconds=1)


class Reloj:
    def __init__(self, ahora: datetime) -> None:
        self.ahora = ahora

    def __call__(self) -> datetime:
        return self.ahora


@pytest.fixture
def datos(app_engine, limpiar) -> None:  # noqa: ANN001
    """Tres invitaciones (una archivada) con teléfonos, historial con alergias, enlace,
    rol, recordatorio, sesión y auditoría."""
    with app_engine.begin() as c:
        a = nueva_invitacion(
            c,
            telefono_principal=TEL,
            contacto_alterno_nombre="Tía Ficticia",
            contacto_alterno_tel=TEL2,
        )
        b = nueva_invitacion(c, telefono_principal=TEL2)
        archivada = nueva_invitacion(
            c, telefono_principal=TEL, archivada_en=datetime(2027, 1, 2, tzinfo=MX)
        )
        nueva_version(c, a, numero=1, vigente=False, alergias="Nueces (ficticio)")
        nueva_version(c, a, numero=2, vigente=True, alergias="Mariscos (ficticio)")
        nueva_version(c, b, numero=1, asiste=False, confirmados=0)
        nueva_version(c, archivada, numero=1, alergias="Gluten (ficticio)")
        c.execute(
            text(
                "INSERT INTO enlace (invitacion_id, hmac_token, token_cifrado, id_llave) "
                "VALUES (:i, :h, :t, 'k1')"
            ),
            {"i": a, "h": b"\x01" * 32, "t": b"\x02" * 44},
        )
        c.execute(text("INSERT INTO invitacion_rol VALUES (:i, 'Padrinos de anillos')"), {"i": a})
        c.execute(
            text(
                "INSERT INTO recordatorio_enviado (invitacion_id, tipo, destino, actor) "
                "VALUES (:i, 'evento', 'principal', 'novia@ejemplo.invalid')"
            ),
            {"i": b},
        )
        c.execute(
            text(
                "INSERT INTO sesion_admin (hash_sesion, correo, secreto_csrf, expira_en) "
                "VALUES (:h, 'novia@ejemplo.invalid', :s, now() + interval '1 day')"
            ),
            {"h": b"\x03" * 32, "s": b"\x04" * 32},
        )
        c.execute(
            text(
                "INSERT INTO evento_auditoria (actor, accion, codigo_invitacion) "
                "VALUES ('novia@ejemplo.invalid', 'invitacion_creada', 'INV-001')"
            )
        )


def _purgar(engine, ahora: datetime):  # noqa: ANN001, ANN202
    with Session(engine) as s, s.begin():
        return purgar(s, Reloj(ahora))


def _conteos(engine) -> dict[str, int]:  # noqa: ANN001
    with Session(engine) as s:
        return contar_tablas(s)


ANTES = {
    "invitacion": 3,
    "invitacion_rol": 1,
    "version_respuesta": 4,
    "enlace": 1,
    "recordatorio_enviado": 1,
    "sesion_admin": 1,
    "evento_auditoria": 1,
    "telefonos": 3,
    "alergias": 3,
}


def test_antes_del_5_de_abril_no_borra_nada(app_engine, datos) -> None:  # noqa: ANN001
    informe = _purgar(app_engine, BORRADO_1 - S)  # 4 abr 23:59:59 en México
    assert informe.fase == "nada que borrar todavía" and informe.cambios == 0
    assert _conteos(app_engine) == ANTES


def test_5_de_abril_telefonos_y_alergias_tambien_en_el_historial(app_engine, datos) -> None:  # noqa: ANN001
    # 5 abr 00:00 en México = 06:00 UTC: cuenta la fecha de México, no la de UTC.
    informe = _purgar(app_engine, BORRADO_1)
    assert (informe.telefonos, informe.alergias, informe.invitaciones) == (3, 3, 0)
    despues = _conteos(app_engine)
    assert despues == ANTES | {"telefonos": 0, "alergias": 0, "evento_auditoria": 2}
    with app_engine.connect() as c:
        assert (
            c.scalar(text("SELECT count(*) FROM invitacion WHERE contacto_alterno_tel IS NOT NULL"))
            == 0
        )
        # El nombre del contacto alterno se borra el 4 jun, con el resto.
        assert (
            c.scalar(
                text("SELECT count(*) FROM invitacion WHERE contacto_alterno_nombre IS NOT NULL")
            )
            == 1
        )
        # La historia de respuestas sigue (sin alergias): asiste y confirmados intactos.
        assert c.scalar(text("SELECT count(*) FROM version_respuesta WHERE vigente")) == 3
        accion, detalle = c.execute(
            text("SELECT accion, detalle FROM evento_auditoria ORDER BY id DESC LIMIT 1")
        ).one()
    assert (
        accion == "purga"
        and detalle["telefonos"] == 3
        and detalle["fase"] == "teléfonos y alergias"
    )
    # Repetible: la segunda corrida del día no cambia nada (ni agrega auditoría).
    assert _purgar(app_engine, BORRADO_1 + timedelta(hours=3)).cambios == 0
    assert _conteos(app_engine) == despues


def test_4_de_junio_no_quedan_datos_personales(app_engine, datos) -> None:  # noqa: ANN001
    _purgar(app_engine, BORRADO_1)
    assert _purgar(app_engine, BORRADO_2 - S).cambios == 0  # 3 jun: nada nuevo
    informe = _purgar(app_engine, BORRADO_2)
    assert (informe.invitaciones, informe.versiones, informe.enlaces) == (3, 4, 1)
    assert (informe.roles, informe.recordatorios, informe.sesiones) == (1, 1, 1)
    assert informe.auditoria == 1  # el evento original (con correo)
    final = _conteos(app_engine)
    # Solo quedan las constancias de la purga (5 abr y 4 jun), sin datos personales.
    assert final == {k: 0 for k in ANTES} | {"evento_auditoria": 2}
    with app_engine.connect() as c:
        filas = c.execute(text("SELECT actor, accion, codigo_invitacion FROM evento_auditoria"))
        assert set(filas) == {("sistema", "purga", None)}
        # La configuración del evento se conserva (no es dato personal).
        assert c.scalar(text("SELECT count(*) FROM configuracion_evento")) == 1
    assert _purgar(app_engine, BORRADO_2 + timedelta(days=30)).cambios == 0
    assert _conteos(app_engine) == final


def test_si_la_purga_del_4_de_junio_corre_sin_la_del_5_de_abril(app_engine, datos) -> None:  # noqa: ANN001
    """Si la tarea no corrió en abril (alerta), la del 4 jun aplica ambas fases."""
    informe = _purgar(app_engine, BORRADO_2)
    assert informe.telefonos == 3 and informe.alergias == 3 and informe.invitaciones == 3
    assert _conteos(app_engine) == {k: 0 for k in ANTES} | {"evento_auditoria": 1}


def test_un_error_no_deja_la_purga_a_medias(app_engine, datos, monkeypatch) -> None:  # noqa: ANN001
    import app.purga as purga

    def roto(s, informe) -> None:  # noqa: ANN001
        s.execute(text("DELETE FROM sesion_admin"))
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(purga, "_borrado_final", roto)
    with pytest.raises(RuntimeError):
        _purgar(app_engine, BORRADO_2)
    assert _conteos(app_engine) == ANTES  # la transacción se revirtió completa
