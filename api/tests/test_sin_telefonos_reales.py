"""Ningún archivo del repo contiene teléfonos con formato real (ADR 0010).

Solo se admiten números de la serie +1 XXX 555-01XX, reservada para ficción.
Revisa los archivos versionados y los nuevos no ignorados (git ls-files).
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BINARIOS = {".webp", ".jpg", ".jpeg", ".png", ".gif", ".ico", ".pdf", ".woff", ".woff2"}
IGNORAR = {"api/uv.lock"}  # solo hashes y versiones

# "+" seguido de 10 a 15 dígitos, con espacios, guiones, puntos o paréntesis opcionales.
CANDIDATO = re.compile(r"\+\s?\(?\d(?:[\s.\-()]*\d){9,14}")
# 10 dígitos agrupados como teléfono nacional (formatos NN NNNN NNNN o NNN-NNN-NNNN).
NACIONAL = re.compile(r"(?<![\d.])\(?\d{2,3}\)?[\s.\-]\d{3,4}[\s.\-]\d{4}(?![\d.])")
FICTICIO = re.compile(r"^\+1\d{3}55501\d{2}$")


def _hallazgos(texto: str) -> list[str]:
    malos, internacionales = [], []
    for m in CANDIDATO.finditer(texto):
        internacionales.append(m.span())
        digitos = "+" + re.sub(r"\D", "", m.group(0))
        if not FICTICIO.fullmatch(digitos):
            malos.append(m.group(0))
    for m in NACIONAL.finditer(texto):
        # Ya evaluado como parte de un número internacional (p. ej. +1 ficticio).
        if any(a <= m.start() < b for a, b in internacionales):
            continue
        digitos = re.sub(r"\D", "", m.group(0))
        if len(digitos) == 10 and not FICTICIO.fullmatch("+1" + digitos):
            malos.append(m.group(0))
    return malos


@pytest.mark.parametrize(
    "muestra",
    # Se arman por partes para que este archivo no contenga el patrón que busca.
    [
        "+52 55 " + "1234 5678",
        "+52" + "5512345678",
        "+52 (444) " + "123-4567",
        "55 1234" + " 5678",
        "444-123" + "-4567",
    ],
)
def test_detecta_formatos_reales(muestra: str) -> None:
    assert _hallazgos(muestra)


@pytest.mark.parametrize(
    "muestra",
    [
        "+12025550123",
        "+1 202 555 0199",
        "2027-03-06T13:00-06:00",
        "60001357",
        "INV-001",
        "sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0",
        "+52",
    ],
)
def test_no_marca_ficticios_ni_otros_numeros(muestra: str) -> None:
    assert not _hallazgos(muestra)


def test_repo_sin_telefonos_reales() -> None:
    salida = subprocess.run(  # noqa: S603
        ["git", "ls-files", "-co", "--exclude-standard"],  # noqa: S607
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    revisados, hallazgos = 0, {}
    for rel in salida:
        ruta = REPO / rel
        if rel in IGNORAR or ruta.suffix.lower() in BINARIOS or not ruta.is_file():
            continue
        revisados += 1
        encontrados = _hallazgos(ruta.read_text(encoding="utf-8", errors="ignore"))
        if encontrados:
            hallazgos[rel] = encontrados
    assert revisados > 20
    assert hallazgos == {}
