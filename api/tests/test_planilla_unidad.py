"""Pruebas sin DB de la lectura de celdas y de la neutralización (I-8). Todo es ficticio."""

import pytest

from app.exportacion import COLUMNAS, neutralizar
from app.planilla import (
    ENCABEZADOS,
    _entero,
    _ErrorCelda,
    _telefono,
    _texto,
    normalizar_encabezado,
)

MX52 = "+" + "52"  # se arma por partes (tests/test_sin_telefonos_reales.py)
TEL = "2025550123"  # serie 555-01XX, ficción


def test_encabezados_exactos_y_normalizados() -> None:
    assert ENCABEZADOS["contacto_alterno_tel"] == "Tel/Celular   de contacto alterno"
    assert normalizar_encabezado("  Tel/Celular   de contacto alterno ") == (
        "Tel/Celular de contacto alterno"
    )
    assert len(COLUMNAS) == 19 and COLUMNAS[0][1] == "Código INV"


@pytest.mark.parametrize(
    ("valor", "esperado"), [(2.0, 2), (3, 3), ("4", 4), ("5.0", 5), (None, None), ("  ", None)]
)
def test_entero(valor: object, esperado: int | None) -> None:
    assert _entero(valor, "x") == esperado


@pytest.mark.parametrize("valor", [2.5, "dos", True, "1,5"])
def test_entero_invalido(valor: object) -> None:
    with pytest.raises(_ErrorCelda):
        _entero(valor, "adultos_invalido")


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (float(TEL), (MX52 + TEL, False)),
        (int(TEL), (MX52 + TEL, False)),
        ("202 555 0123", (MX52 + TEL, False)),
        (TEL + ".0", (MX52 + TEL, False)),
        ("12345", (None, True)),
        (None, (None, False)),
    ],
)
def test_telefono(valor: object, esperado: tuple) -> None:
    assert _telefono(valor) == esperado


@pytest.mark.parametrize(
    "valor", ['=HYPERLINK("http://x.invalid")', "+suma", "-resta", "@arroba", "\tTab", "\rCR"]
)
def test_neutralizar_y_deshacer(valor: str) -> None:
    escrito = neutralizar("comentario", valor)
    assert escrito == "'" + valor
    assert _texto(escrito) == valor  # la importación lo deshace exacto


def test_telefono_e164_no_se_neutraliza() -> None:
    assert neutralizar("telefono_principal", MX52 + TEL) == MX52 + TEL
    assert neutralizar("comentario", MX52 + TEL) == "'" + MX52 + TEL
    assert neutralizar("comentario", "texto normal") == "texto normal"
    assert neutralizar("mesa", 3) == 3
