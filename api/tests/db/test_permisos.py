"""El usuario de EJECUCIÓN no puede crear ni alterar el esquema (ADR 0019, criterio de I-2)."""

import pytest
from sqlalchemy import Connection, Engine, text

from tests.db.conftest import APP, MIGRATOR
from tests.db.util import falla_con, nueva_invitacion, nueva_version

DENEGADO = "42501"  # insufficient_privilege


@pytest.mark.parametrize(
    "ddl",
    [
        "CREATE TABLE intrusa (id int)",
        "CREATE TEMP TABLE intrusa (id int)",
        "CREATE SCHEMA intruso",
        "CREATE VIEW intrusa AS SELECT 1",
        "CREATE FUNCTION intrusa() RETURNS int LANGUAGE sql AS 'SELECT 1'",
        "ALTER TABLE invitacion ADD COLUMN intrusa int",
        "ALTER TABLE invitacion DROP CONSTRAINT invitacion_adultos_min",
        "ALTER TABLE version_respuesta DISABLE TRIGGER version_inmutable",
        "DROP TABLE enlace",
        "DROP INDEX version_una_vigente",
        "CREATE INDEX intruso ON invitacion (nombre_mostrar)",
        "TRUNCATE invitacion CASCADE",
    ],
)
def test_ejecucion_no_puede_ddl(app_conn: Connection, ddl: str) -> None:
    falla_con(app_conn, DENEGADO, ddl)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE version_respuesta SET mensaje = 'x'",  # solo vigente y alergias
        "UPDATE version_respuesta SET confirmados = 1",
        "UPDATE enlace SET invitacion_id = 1",
        "UPDATE configuracion_evento SET cierre_plazo = now()",  # solo lectura (sug.)
        "INSERT INTO configuracion_evento VALUES (1, now(), now(), '2030-01-01', '2030-02-01')",
        "DELETE FROM configuracion_evento",
        "UPDATE evento_auditoria SET accion = 'x'",  # auditoría inmutable
        "UPDATE invitacion_rol SET rol = 'Paje'",
        # sesion_admin: solo ultima_actividad (I-6); correo, CSRF y vencimiento no cambian.
        "UPDATE sesion_admin SET correo = 'x@ejemplo.invalid'",
        "UPDATE sesion_admin SET expira_en = now() + interval '1 year'",
        "UPDATE sesion_admin SET secreto_csrf = decode('00', 'hex')",
        "UPDATE sesion_admin SET hash_sesion = hash_sesion",
        # recordatorio_enviado (I-7): historial; se inserta y se lee, nunca se modifica.
        "UPDATE recordatorio_enviado SET tipo = 'evento'",
        "UPDATE configuracion_evento SET cierre_planner = now()",
        # alembic_version y secuencias: solo LECTURA para pg_dump (migración 0006, I-10).
        "UPDATE alembic_version SET version_num = 'x'",
        "DELETE FROM alembic_version",
        "SELECT setval(pg_get_serial_sequence('invitacion', 'id'), 999)",
    ],
)
def test_ejecucion_sin_permisos_de_datos_fuera_de_lo_otorgado(
    app_conn: Connection, sql: str
) -> None:
    falla_con(app_conn, DENEGADO, sql)


def test_ejecucion_si_puede_operar_datos(app_conn: Connection) -> None:
    inv = nueva_invitacion(app_conn)
    v = nueva_version(app_conn, inv)
    app_conn.execute(text("UPDATE version_respuesta SET vigente = false WHERE id = :v"), {"v": v})
    app_conn.execute(text("UPDATE invitacion SET mesa = 4 WHERE id = :i"), {"i": inv})
    app_conn.execute(text("SELECT * FROM configuracion_evento")).one()
    app_conn.execute(
        text("INSERT INTO evento_auditoria (actor, accion) VALUES ('a@ejemplo.invalid', 'prueba')")
    )
    app_conn.execute(text("UPDATE sesion_admin SET ultima_actividad = now()"))  # I-6
    app_conn.execute(  # I-7
        text(
            "INSERT INTO recordatorio_enviado (invitacion_id, tipo, destino, actor) "
            "VALUES (:i, 'confirmar', 'principal', 'p@ejemplo.invalid')"
        ),
        {"i": inv},
    )
    app_conn.execute(text("SELECT * FROM recordatorio_enviado")).all()


def test_atributos_de_los_roles(migrator_engine: Engine) -> None:
    with migrator_engine.connect() as conn:
        filas = conn.execute(
            text(
                "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
                "FROM pg_roles WHERE rolname IN (:a, :m) ORDER BY rolname"
            ),
            {"a": APP, "m": MIGRATOR},
        ).all()
        assert [tuple(f[1:]) for f in filas] == [(False, False, False, False)] * 2
        # Todas las tablas pertenecen al usuario de migraciones.
        duenos = (
            conn.execute(
                text("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'public'")
            )
            .scalars()
            .all()
        )
        assert duenos == [MIGRATOR]


def test_ejecucion_no_puede_otorgar_permisos(app_conn: Connection) -> None:
    # Postgres no da error si quien no es dueño intenta un GRANT: avisa y no otorga nada.
    app_conn.execute(text("GRANT SELECT ON invitacion TO PUBLIC"))
    otorgados = app_conn.scalar(
        text(
            "SELECT count(*) FROM information_schema.role_table_grants "
            "WHERE grantee = 'PUBLIC' AND table_schema = 'public'"
        )
    )
    assert otorgados == 0
