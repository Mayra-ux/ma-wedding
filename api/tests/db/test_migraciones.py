"""`migrate` crea el esquema desde cero con el usuario de migraciones y es repetible."""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app import migrar
from app.models import Base
from tests.db.conftest import APP, borrar_base, crear_base, urls

HEAD = "0002"  # última migración

TABLAS = {
    "configuracion_evento",
    "invitacion",
    "invitacion_rol",
    "version_respuesta",
    "enlace",
    "sesion_admin",
    "evento_auditoria",
}


def _estado(url: str) -> tuple[set[str], str | None]:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            tablas = set(inspect(conn).get_table_names()) - {"alembic_version"}
            version = (
                conn.scalar(text("SELECT version_num FROM alembic_version"))
                if inspect(conn).has_table("alembic_version")
                else None
            )
        return tablas, version
    finally:
        engine.dispose()


def test_migrate_desde_cero_y_repetible(admin_engine) -> None:
    name = crear_base(admin_engine)
    u = urls(name)
    try:
        assert _estado(u["migrator"]) == (set(), None)
        migrar.upgrade(u["migrator"], APP)
        assert _estado(u["migrator"]) == (TABLAS, HEAD)
        migrar.upgrade(u["migrator"], APP)  # segunda vez: no hace nada y no falla
        assert _estado(u["migrator"]) == (TABLAS, HEAD)
        migrar.downgrade_base(u["migrator"], APP)
        assert _estado(u["migrator"])[0] == set()
        migrar.upgrade(u["migrator"], APP)  # y se vuelve a crear igual
        assert _estado(u["migrator"]) == (TABLAS, HEAD)
    finally:
        borrar_base(admin_engine, name)


def test_el_usuario_de_ejecucion_no_puede_migrar(admin_engine) -> None:
    name = crear_base(admin_engine)
    u = urls(name)
    try:
        with pytest.raises(DBAPIError) as info:
            migrar.upgrade(u["app"], APP)
        assert info.value.orig.sqlstate == "42501"
        assert _estado(u["migrator"]) == (set(), None)
    finally:
        borrar_base(admin_engine, name)


def test_modelos_coinciden_con_la_db(migrator_engine) -> None:
    with migrator_engine.connect() as conn:
        insp = inspect(conn)
        for tabla in Base.metadata.sorted_tables:
            en_db = {c["name"] for c in insp.get_columns(tabla.name)}
            assert set(tabla.columns.keys()) == en_db, tabla.name
