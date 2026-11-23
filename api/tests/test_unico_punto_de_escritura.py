"""La API es el único punto de escritura de la base (I-7, requisito de los novios; ADR 0019, 0026).

- La base no se publica fuera de la red de compose.
- El servicio `api` solo recibe la conexión del usuario de EJECUCIÓN (privilegios mínimos);
  las credenciales de migraciones solo las recibe el servicio `migrate`.
- El código de la API no usa la conexión de migraciones, salvo el comando `migrate`.
Los privilegios del usuario de ejecución los prueba tests/db/test_permisos.py, y la guardia
de escrituras del panel (solo novios), tests/db/test_auth_panel.py.
"""

import importlib.util
import re
from pathlib import Path

import pytest

from app.catalogos import GRUPOS, LADOS, MOTIVOS_REVISION, ROLES_BODA
from app.errores import ErrorAPI
from app.invitaciones import fecha_larga, normalizar_telefono

API = Path(__file__).resolve().parent.parent
REPO = API.parent


def _servicio(nombre: str) -> str:
    """Bloque de texto de un servicio de compose.yaml (sin dependencias de YAML)."""
    lineas = (REPO / "compose.yaml").read_text(encoding="utf-8").splitlines()
    inicio = lineas.index(f"  {nombre}:")
    bloque = []
    for linea in lineas[inicio + 1 :]:
        if re.match(r"^  \S", linea) or re.match(r"^\S", linea):
            break
        bloque.append(linea)
    return "\n".join(bloque)


def _sin_comentarios(texto: str) -> str:
    return "\n".join(linea.split("#", 1)[0] for linea in texto.splitlines())


def test_la_base_no_publica_puertos() -> None:
    assert not re.search(r"^\s+ports:", _sin_comentarios(_servicio("db")), re.MULTILINE)


def test_la_api_solo_recibe_el_usuario_de_ejecucion() -> None:
    api = _sin_comentarios(_servicio("api"))
    assert "DATABASE_URL" in api and "DB_RUNTIME_ROLE" in api
    assert "MIGRATION_DATABASE_URL" not in api and "DB_MIGRATOR" not in api
    migrate = _sin_comentarios(_servicio("migrate"))
    assert "MIGRATION_DATABASE_URL" in migrate


def test_el_codigo_de_la_api_no_usa_la_conexion_de_migraciones() -> None:
    usos = sorted(
        p.name
        for p in (API / "app").glob("*.py")
        if "migration_database_url" in p.read_text(encoding="utf-8")
    )
    # Solo los comandos `migrate` y `restaurar` (base NUEVA, I-10) y su definición.
    assert usos == ["__main__.py", "config.py"]


# --------------------------------------------------------------------------- catálogos
def test_catalogos_coinciden_con_la_migracion() -> None:
    ruta = API / "migrations" / "versions" / "0001_esquema_inicial.py"
    spec = importlib.util.spec_from_file_location("m0001", ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    texto = ruta.read_text(encoding="utf-8")
    assert m.ROLES_BODA == ROLES_BODA and m.MOTIVOS_REVISION == MOTIVOS_REVISION
    assert "lado IN ('Novia', 'Novio', 'Ambos')" in texto and LADOS == ("Novia", "Novio", "Ambos")
    assert "grupo IN ('Familia', 'Amigos', 'Trabajo', 'Otro')" in texto
    assert GRUPOS == ("Familia", "Amigos", "Trabajo", "Otro")


# --------------------------------------------------------------------------- teléfonos y fechas
TEL = "2025550123"  # serie 555-01XX, reservada para ficción
MX52 = "+" + "52"  # se arma por partes (tests/test_sin_telefonos_reales.py)
UK = "+" + "44"


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (TEL, MX52 + TEL),
        ("202 555 0123", MX52 + TEL),
        ("(202) 555-0123", MX52 + TEL),
        (MX52 + " " + TEL, MX52 + TEL),
        ("00" + "52" + TEL, MX52 + TEL),
        ("+1 202 555 0199", "+12025550199"),
        (UK + " 20 " + "7946 0000", UK + "20" + "79460000"),
        ("", None),
        (None, None),
    ],
)
def test_normalizar_telefono(entrada: str | None, esperado: str | None) -> None:
    assert normalizar_telefono(entrada, "telefono_principal") == esperado


@pytest.mark.parametrize("entrada", ["12345", "202555012", "20255501234", "+0123", "abc"])
def test_telefono_invalido(entrada: str) -> None:
    with pytest.raises(ErrorAPI) as info:
        normalizar_telefono(entrada, "telefono_principal")
    assert info.value.fields == {"telefono_principal": "telefono_invalido"}


def test_fecha_larga_en_espanol() -> None:
    from datetime import date

    assert fecha_larga(date(2027, 1, 30)) == "sábado 30 de enero de 2027"
    assert fecha_larga(date(2027, 3, 6)) == "sábado 6 de marzo de 2027"
