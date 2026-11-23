"""Borrado programado de datos personales (I-10; ADR 0010, doc 04 §4.6, reglas F5, F6 y F10).

Tarea diaria e idempotente con el usuario de ejecución. Lee las fechas de la configuración del
evento y la fecha de hoy en hora del centro de México (−06:00):

- Hoy ≥ `fecha_borrado_1` (5 abr 2027): borra teléfonos (principal y contacto alterno) de todas
  las invitaciones, incluidas las archivadas, y las alergias de TODAS las versiones (historial).
- Hoy ≥ `fecha_borrado_2` (4 jun 2027): borra las invitaciones (con sus roles, versiones,
  enlaces y recordatorios), las sesiones del panel y la auditoría (lleva correos), salvo
  las constancias de la purga (actor 'sistema', solo conteos).

Cada paso es una transacción. El informe solo tiene conteos. Es el único módulo que puede
borrar invitaciones (app/guardas.py; tests/test_sin_delete_invitacion.py).
"""

from dataclasses import asdict, dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.estado import MX, Reloj
from app.guardas import PURGA


@dataclass
class InformePurga:
    hoy: date
    fecha_borrado_1: date
    fecha_borrado_2: date
    telefonos: int = 0  # invitaciones a las que se les quitó al menos un teléfono
    alergias: int = 0  # versiones (vigentes o históricas) a las que se les quitaron
    invitaciones: int = 0
    versiones: int = 0
    enlaces: int = 0
    roles: int = 0
    recordatorios: int = 0
    sesiones: int = 0
    auditoria: int = 0

    @property
    def fase(self) -> str:
        if self.hoy >= self.fecha_borrado_2:
            return "borrado final"
        if self.hoy >= self.fecha_borrado_1:
            return "teléfonos y alergias"
        return "nada que borrar todavía"

    @property
    def cambios(self) -> int:
        return sum(
            v for k, v in asdict(self).items() if isinstance(v, int) and not isinstance(v, bool)
        )

    def texto(self) -> str:
        cuentas = {k: v for k, v in asdict(self).items() if isinstance(v, int)}
        return (
            f"purge {self.hoy.isoformat()} · fase: {self.fase} · "
            f"fechas {self.fecha_borrado_1.isoformat()} y {self.fecha_borrado_2.isoformat()} · "
            + " · ".join(f"{k} {v}" for k, v in cuentas.items())
        )


def hoy_mx(reloj: Reloj) -> date:
    return reloj().astimezone(MX).date()


def _contar(s: Session, sql: str) -> int:
    return int(s.execute(text(sql)).scalar_one())


def _fechas(s: Session) -> tuple[date, date]:
    fila = s.execute(
        text("SELECT fecha_borrado_1, fecha_borrado_2 FROM configuracion_evento WHERE id = 1")
    ).one()
    return fila[0], fila[1]


def _telefonos_y_alergias(s: Session, informe: InformePurga) -> None:
    informe.telefonos = s.execute(
        text(
            "UPDATE invitacion SET telefono_principal = NULL, contacto_alterno_tel = NULL "
            "WHERE telefono_principal IS NOT NULL OR contacto_alterno_tel IS NOT NULL"
        )
    ).rowcount
    informe.alergias = s.execute(
        text("UPDATE version_respuesta SET alergias = NULL WHERE alergias IS NOT NULL")
    ).rowcount


def _borrado_final(s: Session, informe: InformePurga) -> None:
    informe.versiones = _contar(s, "SELECT count(*) FROM version_respuesta")
    informe.enlaces = _contar(s, "SELECT count(*) FROM enlace")
    informe.roles = _contar(s, "SELECT count(*) FROM invitacion_rol")
    informe.recordatorios = _contar(s, "SELECT count(*) FROM recordatorio_enviado")
    # ON DELETE CASCADE borra roles, versiones, enlaces y recordatorios.
    informe.invitaciones = s.execute(text("DELETE FROM invitacion")).rowcount
    informe.sesiones = s.execute(text("DELETE FROM sesion_admin")).rowcount
    # La auditoría lleva correos: se borra toda salvo las constancias de la propia purga
    # (actor 'sistema', solo conteos), para que la corrida diaria siguiente no cambie nada.
    informe.auditoria = s.execute(
        text("DELETE FROM evento_auditoria WHERE actor <> 'sistema'")
    ).rowcount


def purgar(s: Session, reloj: Reloj) -> InformePurga:
    """Aplica lo que toque según la fecha. `s` debe estar dentro de una transacción."""
    s.info[PURGA] = True
    try:
        f1, f2 = _fechas(s)
        informe = InformePurga(hoy=hoy_mx(reloj), fecha_borrado_1=f1, fecha_borrado_2=f2)
        if informe.hoy >= f1:
            _telefonos_y_alergias(s, informe)
        if informe.hoy >= f2:
            _borrado_final(s, informe)
        if informe.cambios:
            # Constancia sin datos personales (después del borrado final queda solo esta).
            s.execute(
                text(
                    "INSERT INTO evento_auditoria (actor, accion, detalle) "
                    "VALUES ('sistema', 'purga', CAST(:d AS jsonb))"
                ),
                {"d": _json_conteos(informe)},
            )
        return informe
    finally:
        s.info.pop(PURGA, None)


def _json_conteos(informe: InformePurga) -> str:
    import json

    datos = {k: v for k, v in asdict(informe).items() if isinstance(v, int)}
    return json.dumps({"fase": informe.fase, **datos})


def contar_tablas(s: Session) -> dict[str, int]:
    """Conteos por tabla (sin datos personales): informe del respaldo y de la restauración."""
    tablas = (
        "invitacion",
        "invitacion_rol",
        "version_respuesta",
        "enlace",
        "recordatorio_enviado",
        "sesion_admin",
        "evento_auditoria",
    )
    cuentas = {t: _contar(s, f"SELECT count(*) FROM {t}") for t in tablas}  # noqa: S608
    cuentas["telefonos"] = _contar(
        s,
        "SELECT count(*) FROM invitacion "
        "WHERE telefono_principal IS NOT NULL OR contacto_alterno_tel IS NOT NULL",
    )
    cuentas["alergias"] = _contar(
        s, "SELECT count(*) FROM version_respuesta WHERE alergias IS NOT NULL"
    )
    return cuentas
