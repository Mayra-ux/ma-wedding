"""Ningún código de la aplicación fuera de la purga borra invitaciones (ADR 0017: se archivan).

Complementa la guarda en tiempo de ejecución (app/guardas.py, tests/db/test_guardas.py):
este test revisa el código fuente, incluido el SQL de texto que la guarda no ve.
"""

import re
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent / "app"
PERMITIDOS = {"purga.py"}  # módulo de la purga (fase I-10)

PATRONES = [
    re.compile(r"\bDELETE\s+FROM\s+(?:ONLY\s+)?(?:\"?public\"?\.)?\"?invitacion\"?\b", re.I),
    re.compile(r"\bdelete\s*\(\s*(?:models\.)?Invitacion\b"),
    re.compile(r"query\s*\(\s*(?:models\.)?Invitacion\b[^\n]*\.delete\s*\("),
    re.compile(
        r"\bTRUNCATE\s+(?:TABLE\s+)?(?:ONLY\s+)?(?:\"?public\"?\.)?\"?invitacion\"?\b", re.I
    ),
]


def _buscar(fuente: str) -> list[str]:
    return [m.group(0) for p in PATRONES for m in p.finditer(fuente)]


@pytest.mark.parametrize(
    "muestra",
    [
        'conn.execute(text("DELETE FROM invitacion WHERE id = :i"))',
        "delete from public.invitacion",
        "session.execute(delete(Invitacion).where(Invitacion.id == 1))",
        "session.query(Invitacion).filter_by(id=1).delete()",
        "TRUNCATE TABLE invitacion",
    ],
)
def test_los_patrones_detectan_borrados(muestra: str) -> None:
    assert _buscar(muestra)


@pytest.mark.parametrize(
    "muestra",
    [
        "DELETE FROM invitacion_rol WHERE invitacion_id = :i",
        "delete(InvitacionRol)",
        "UPDATE invitacion SET archivada_en = now()",
    ],
)
def test_los_patrones_no_dan_falsos_positivos(muestra: str) -> None:
    assert not _buscar(muestra)


def test_ningun_modulo_fuera_de_la_purga_borra_invitaciones() -> None:
    archivos = [p for p in APP_DIR.rglob("*.py") if p.name not in PERMITIDOS]
    assert archivos, "no se encontró código de la aplicación"
    hallazgos = {
        str(p.relative_to(APP_DIR)): encontrados
        for p in archivos
        if (encontrados := _buscar(p.read_text(encoding="utf-8")))
    }
    assert hallazgos == {}
