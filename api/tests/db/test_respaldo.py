"""Respaldo → base NUEVA → purga → la API arranca y los conteos coinciden (criterio de I-10).

Usa `pg_dump` y `pg_restore` REALES: los del contenedor `db-test` (postgres:16), mediante
`docker exec`, así que no hace falta instalar el cliente de Postgres en el equipo. El cifrado
con `age` se simula aquí (agrega la cabecera de age); el `age` real se prueba en la imagen
(modo «como producción»). Datos ficticios.
"""

import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import migrar
from app.config import Settings
from app.db import make_sessionmaker
from app.estado import MX
from app.main import create_app
from app.purga import contar_tablas
from app.respaldo import (
    CABECERA_AGE,
    DestinoCarpeta,
    ErrorRespaldo,
    clave_informe,
    respaldar,
    restaurar,
    verificar_restauracion,
)
from tests.db.conftest import APP, borrar_base, crear_base, urls
from tests.db.test_purga import Reloj
from tests.db.util import invitacion_con_enlace, llaves_de_prueba, nueva_version
from tests.test_respaldo_unidad import s3  # noqa: F401  (fixture del S3 simulado)

CONTENEDOR = "ma-wedding-db-test-1"
TEL = "+" + "52" + "2025550123"
MARZO = datetime(2027, 3, 1, 2, 30, tzinfo=MX)
BORRADO_1 = datetime(2027, 4, 5, 2, 30, tzinfo=MX)
BORRADO_2 = datetime(2027, 6, 4, 2, 30, tzinfo=MX)
RECIPIENT = "age1" + "q" * 58


def _docker_listo() -> bool:
    if not shutil.which("docker"):
        return False
    r = subprocess.run(  # noqa: S603
        ["docker", "inspect", "-f", "{{.State.Running}}", CONTENEDOR],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return r.stdout.strip() == "true"


pytestmark = pytest.mark.skipif(not _docker_listo(), reason="db-test no está corriendo en Docker")


def _pg(url: str, programa: str, *args: str, entrada: bytes | None = None) -> bytes:
    u = make_url(url)
    p = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "docker",
            "exec",
            "-i",
            "-e",
            f"PGPASSWORD={u.password}",
            CONTENEDOR,
            programa,
            "-h",
            "localhost",
            "-p",
            "5432",
            "-U",
            u.username,
            "-d",
            u.database,
            *args,
        ],
        input=entrada,
        capture_output=True,
        check=False,
    )
    if p.returncode != 0:
        raise ErrorRespaldo(programa, p.stderr.decode()[-300:])
    return p.stdout


def volcar(url: str, instantanea: str) -> bytes:
    return _pg(url, "pg_dump", "--format=custom", "--no-owner", f"--snapshot={instantanea}")


def cargar(url: str, volcado: bytes) -> None:
    _pg(url, "pg_restore", "--no-owner", "--exit-on-error", "--single-transaction", entrada=volcado)


def cifrar(datos: bytes, destinatario: str) -> bytes:
    assert destinatario == RECIPIENT
    return CABECERA_AGE + datos[::-1]


def descifrar(datos: bytes, identidad: Path) -> bytes:
    assert datos.startswith(CABECERA_AGE)
    return datos[len(CABECERA_AGE) :][::-1]


@pytest.fixture
def bases(admin_engine):  # noqa: ANN001, ANN201
    creadas: list[str] = []
    motores = []

    def nueva(migrada: bool = True) -> dict:
        nombre = crear_base(admin_engine)
        creadas.append(nombre)
        u = urls(nombre)
        if migrada:
            migrar.upgrade(u["migrator"], APP)
        u["engine_app"] = create_engine(u["app"])
        u["engine_migrator"] = create_engine(u["migrator"])
        motores.extend([u["engine_app"], u["engine_migrator"]])
        return u

    yield nueva
    for m in motores:
        m.dispose()
    for nombre in creadas:
        borrar_base(admin_engine, nombre)


def _poblar(engine, llaves) -> str:  # noqa: ANN001
    datos = invitacion_con_enlace(engine, llaves, telefono_principal=TEL)
    with engine.begin() as c:
        nueva_version(c, datos["id"], numero=1, vigente=False, alergias="Nueces (ficticio)")
        nueva_version(c, datos["id"], numero=2, vigente=True, alergias="Ninguna (ficticio)")
    invitacion_con_enlace(engine, llaves, nombre_mostrar="Familia Ficticia Dos")
    return datos["token"]


def test_respaldo_restauracion_y_verificacion(bases, tmp_path) -> None:  # noqa: ANN001
    llaves = llaves_de_prueba()
    origen = bases()
    token = _poblar(origen["engine_app"], llaves)
    destino = DestinoCarpeta(tmp_path)

    informe = respaldar(
        origen["engine_app"], origen["app"], destino, RECIPIENT, Reloj(MARZO), volcar, cifrar
    )
    assert (
        informe.clave.startswith("vence-2027-04-05/") and informe.vence.isoformat() == "2027-04-05"
    )
    assert destino.listar() == sorted([informe.clave, clave_informe(informe.clave)])
    cifrado = destino.bajar(informe.clave)
    assert cifrado.startswith(CABECERA_AGE) and b"PGDMP" not in cifrado[:64]
    with Session(origen["engine_app"]) as s:
        assert informe.conteos == contar_tablas(s)
    assert informe.conteos["telefonos"] == 1 and informe.conteos["alergias"] == 2
    guardado = json.loads(destino.bajar(clave_informe(informe.clave)))
    assert guardado["conteos"] == informe.conteos and guardado["migracion"] == "0006"
    assert TEL not in json.dumps(guardado)  # el informe no lleva datos personales

    # ---- base NUEVA y vacía (sin migrar): pg_restore con el usuario de migraciones (dueño)
    nueva = bases(migrada=False)
    restaurar(
        nueva["engine_migrator"],
        nueva["migrator"],
        destino,
        informe.clave,
        Path("id.txt"),
        descifrar,
        cargar,
    )
    verif = verificar_restauracion(nueva["engine_app"], guardado, Reloj(MARZO))
    assert verif.correcta, verif.texto()
    assert verif.purga.cambios == 0 and "conteos coinciden" in verif.texto()

    # ---- la API arranca sobre la base restaurada y, con la misma llave, el enlace funciona
    app = create_app(
        Settings(invitation_origin="https://ma-wedding-six.vercel.app"),
        sesiones=make_sessionmaker(nueva["engine_app"]),
        llaves=llaves,
        reloj=Reloj(MARZO),
    )
    cliente = TestClient(app)
    assert cliente.get("/health").status_code == 200
    r = cliente.post("/api/v1/public/invitation/lookup", json={"token": token})
    assert r.status_code == 200 and r.json()["estado"] == "congelada"

    # ---- nunca pisa una base con datos
    with pytest.raises(ErrorRespaldo, match="no está vacía"):
        restaurar(
            nueva["engine_migrator"],
            nueva["migrator"],
            destino,
            informe.clave,
            Path("id.txt"),
            descifrar,
            cargar,
        )


def test_restaurar_despues_del_5_de_abril_purga_antes_de_abrir(bases, tmp_path) -> None:  # noqa: ANN001
    """F9: un respaldo de marzo restaurado el 5 abr no reintroduce teléfonos ni alergias."""
    origen = bases()
    _poblar(origen["engine_app"], llaves_de_prueba())
    destino = DestinoCarpeta(tmp_path)
    informe = respaldar(
        origen["engine_app"], origen["app"], destino, RECIPIENT, Reloj(MARZO), volcar, cifrar
    )
    nueva = bases(migrada=False)
    restaurar(
        nueva["engine_migrator"],
        nueva["migrator"],
        destino,
        informe.clave,
        Path("i"),
        descifrar,
        cargar,
    )
    verif = verificar_restauracion(
        nueva["engine_app"], json.loads(informe.json()), Reloj(BORRADO_1)
    )
    assert verif.correcta, verif.texto()
    assert (verif.purga.telefonos, verif.purga.alergias) == (1, 2)
    assert verif.obtenido["telefonos"] == 0 and verif.obtenido["alergias"] == 0


def test_respaldo_alterado_no_se_restaura(bases, tmp_path) -> None:  # noqa: ANN001
    origen = bases()
    destino = DestinoCarpeta(tmp_path)
    informe = respaldar(
        origen["engine_app"], origen["app"], destino, RECIPIENT, Reloj(MARZO), volcar, cifrar
    )
    destino.subir(informe.clave, destino.bajar(informe.clave) + b"x")
    nueva = bases(migrada=False)
    with pytest.raises(ErrorRespaldo, match="sha256"):
        restaurar(
            nueva["engine_migrator"],
            nueva["migrator"],
            destino,
            informe.clave,
            Path("i"),
            descifrar,
            cargar,
        )


def test_vencimientos_y_limpieza_en_el_destino(bases, s3) -> None:  # noqa: ANN001, F811
    """S3 simulado: prefijo por vencimiento y borrado de lo vencido (además de R2)."""
    origen = bases()
    a = respaldar(origen["engine_app"], origen["app"], s3, RECIPIENT, Reloj(MARZO), volcar, cifrar)
    b = respaldar(
        origen["engine_app"],
        origen["app"],
        s3,
        RECIPIENT,
        Reloj(BORRADO_1 - timedelta(days=1)),
        volcar,
        cifrar,
    )
    assert a.vence == b.vence and len(s3.listar()) == 4
    c = respaldar(
        origen["engine_app"], origen["app"], s3, RECIPIENT, Reloj(BORRADO_1), volcar, cifrar
    )
    assert c.clave.startswith("vence-2027-06-04/")
    assert sorted(c.borrados) == sorted(
        [a.clave, clave_informe(a.clave), b.clave, clave_informe(b.clave)]
    )
    assert s3.listar() == sorted([c.clave, clave_informe(c.clave)])
    d = respaldar(
        origen["engine_app"], origen["app"], s3, RECIPIENT, Reloj(BORRADO_2), volcar, cifrar
    )
    assert d.clave is None and "ya pasó el borrado final" in d.texto()
    assert s3.listar() == []  # el 4 jun no queda ningún respaldo


def test_sin_llave_publica_no_respalda(bases, tmp_path) -> None:  # noqa: ANN001
    origen = bases()
    with pytest.raises(ErrorRespaldo, match="BACKUP_AGE_RECIPIENT"):
        respaldar(origen["engine_app"], origen["app"], DestinoCarpeta(tmp_path), None, Reloj(MARZO))


def test_un_cifrado_que_no_es_age_se_rechaza(bases, tmp_path) -> None:  # noqa: ANN001
    origen = bases()
    destino = DestinoCarpeta(tmp_path)
    with pytest.raises(ErrorRespaldo, match="cifrado"):
        respaldar(
            origen["engine_app"],
            origen["app"],
            destino,
            RECIPIENT,
            Reloj(MARZO),
            volcar,
            lambda datos, r: datos,  # «cifrado» que deja el volcado en claro
        )
    assert destino.listar() == []


def test_el_usuario_de_ejecucion_solo_lee_para_respaldar(bases) -> None:  # noqa: ANN001
    origen = bases()
    with origen["engine_app"].connect() as c:
        for sql in (
            "UPDATE alembic_version SET version_num = 'x'",
            "SELECT setval(pg_get_serial_sequence('invitacion', 'id'), 999)",
        ):
            with pytest.raises(Exception) as info, c.begin_nested():  # noqa: PT011
                c.execute(text(sql))
            assert info.value.orig.sqlstate == "42501"
