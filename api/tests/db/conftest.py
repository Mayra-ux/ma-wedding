"""Fixtures de la DB de pruebas (servicio `db-test` de compose, descartable).

Cada corrida crea una base nueva, la migra con el usuario de MIGRACIONES y prueba
con el usuario de EJECUCIÓN, igual que en producción (ADR 0019). Todo es ficticio.
"""

import os
import secrets
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import migrar

ADMIN_URL = os.environ.get(
    "TEST_ADMIN_URL",
    "postgresql+psycopg://ma_test_admin:ma_test_solo_local@127.0.0.1:55432/postgres",
)
MIGRATOR, MIGRATOR_PW = "ma_test_migrator", "migrator_solo_test"
APP, APP_PW = "ma_test_app", "app_solo_test"

DATA_TABLES = (
    "invitacion, invitacion_rol, version_respuesta, enlace, sesion_admin, evento_auditoria"
)


def _url(user: str, password: str, db: str) -> str:
    return (
        make_url(ADMIN_URL)
        .set(username=user, password=password, database=db)
        .render_as_string(hide_password=False)
    )


@pytest.fixture(scope="session")
def admin_engine() -> Iterator[Engine]:
    engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        engine.connect().close()
    except OperationalError:
        pytest.fail(
            "db-test no responde en 127.0.0.1:55432. "
            "Levántalo con: docker compose --profile test up -d --wait db-test"
        )
    with engine.connect() as conn:
        for role, pw in ((MIGRATOR, MIGRATOR_PW), (APP, APP_PW)):
            exists = conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role})
            if not exists:
                conn.execute(
                    text(
                        f"CREATE ROLE {role} LOGIN PASSWORD '{pw}' "
                        "NOSUPERUSER NOCREATEDB NOCREATEROLE"
                    )
                )
    yield engine
    engine.dispose()


def crear_base(admin_engine: Engine) -> str:
    """Base vacía, propiedad del usuario de migraciones (como db/init/01-roles.sh)."""
    name = "ma_test_" + secrets.token_hex(4)
    with admin_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {name} OWNER {MIGRATOR}"))
        conn.execute(text(f"REVOKE ALL ON DATABASE {name} FROM PUBLIC"))
        conn.execute(text(f"GRANT CONNECT ON DATABASE {name} TO {MIGRATOR}, {APP}"))
    return name


def borrar_base(admin_engine: Engine, name: str) -> None:
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))


def urls(name: str) -> dict[str, str]:
    return {"migrator": _url(MIGRATOR, MIGRATOR_PW, name), "app": _url(APP, APP_PW, name)}


@pytest.fixture(scope="session")
def base(admin_engine: Engine) -> Iterator[dict[str, str]]:
    name = crear_base(admin_engine)
    u = urls(name)
    migrar.upgrade(u["migrator"], APP)
    yield u
    borrar_base(admin_engine, name)


@pytest.fixture(scope="session")
def migrator_engine(base: dict[str, str]) -> Iterator[Engine]:
    engine = create_engine(base["migrator"])
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def app_engine(base: dict[str, str]) -> Iterator[Engine]:
    engine = create_engine(base["app"])
    yield engine
    engine.dispose()


@pytest.fixture
def app_conn(app_engine: Engine) -> Iterator[Connection]:
    """Conexión del usuario de ejecución dentro de una transacción que se revierte."""
    conn = app_engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()


@pytest.fixture
def limpiar(migrator_engine: Engine) -> Iterator[None]:
    """Para tests que necesitan datos confirmados (concurrencia): vacía las tablas al final."""
    yield
    with migrator_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {DATA_TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture
def sesion(app_conn: Connection) -> Iterator[Session]:
    """Sesión ORM del usuario de ejecución sobre `app_conn` (todo se revierte al final)."""
    s = Session(bind=app_conn, join_transaction_mode="create_savepoint")
    try:
        yield s
    finally:
        s.close()
