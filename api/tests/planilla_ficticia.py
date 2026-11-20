"""Archivos FICTICIOS con la estructura real del Excel de la planner (I-8, ADR 0028).

Nunca se usa el Excel real. Estructura: hojas "Lista de invitados" (novio) y "Copia de Lista
de invitados" (novia) + hojas que no son de invitados; título en B1; encabezados exactos en la
fila 2 desde la columna B (A vacía); ~220 filas con formato y pocas con datos; números como
decimales (2.0); teléfonos como número o como texto con espacios. Teléfonos de la serie
555-01XX (reservada para ficción).
"""

import csv
import io
import zipfile

import openpyxl
from openpyxl.styles import Border, Side

from app.planilla import ENCABEZADOS, EXTRAS

TITULO = "Lista de invitados Mayra y Alejandro"
HOJA_NOVIO = "Lista de invitados"
HOJA_NOVIA = "Copia de Lista de invitados"
TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
COLUMNAS = list(ENCABEZADOS)  # claves en el orden B..O


def fila(**valores) -> dict:  # noqa: ANN003
    return valores


def _llenar(ws, filas: list[dict], extras: tuple[str, ...] = (), filas_formato: int = 220) -> None:  # noqa: ANN001
    ws["B1"] = TITULO
    claves = COLUMNAS + list(extras)
    for j, clave in enumerate(claves, start=2):
        ws.cell(row=2, column=j, value=ENCABEZADOS.get(clave) or EXTRAS[clave])
    borde = Border(bottom=Side(style="thin"))
    for r in range(3, 3 + filas_formato):  # filas de formato sin datos
        for j in range(2, 2 + len(claves)):
            ws.cell(row=r, column=j).border = borde
    for i, datos in enumerate(filas):
        for j, clave in enumerate(claves, start=2):
            if clave in datos:
                ws.cell(row=3 + i, column=j, value=datos[clave])


def libro(
    novio: list[dict] | None = None,
    novia: list[dict] | None = None,
    extras: tuple[str, ...] = (),
) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = HOJA_NOVIO
    _llenar(ws, novio or [], extras)
    if novia is not None:
        _llenar(wb.create_sheet(HOJA_NOVIA), novia, extras)
    # Hojas que no son de invitados (deben ignorarse).
    p = wb.create_sheet("Presupuesto")
    p.append(["Concepto", "Monto"])
    p.append(["Flores", 1500.0])
    pl = wb.create_sheet("Playlist")
    pl.append(["Canción", "Momento"])
    pi = wb.create_sheet("Personas importantes")
    pi.append(["Nombre", "Rol"])
    pi.append(["Persona Ficticia", "Fotógrafo"])
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def csv_planner(filas: list[dict], separador: str = ";", codificacion: str = "cp1252") -> bytes:
    texto = io.StringIO()
    w = csv.writer(texto, delimiter=separador, lineterminator="\r\n")
    w.writerow(["", TITULO])
    w.writerow(["", *(ENCABEZADOS[k] for k in COLUMNAS)])
    for datos in filas:
        w.writerow(["", *("" if datos.get(k) is None else datos[k] for k in COLUMNAS)])
    w.writerow([""] * 15)
    return texto.getvalue().encode(codificacion)


def modificar(contenido: bytes, cambios: dict[tuple[str, str], object]) -> bytes:
    """Cambia celdas de un .xlsx exportado: {(codigo, encabezado): valor}."""
    wb = openpyxl.load_workbook(io.BytesIO(contenido))
    ws = wb.active
    encabezados = [c.value for c in ws[1]]
    for row in ws.iter_rows(min_row=2):
        codigo = row[0].value
        for (c, enc), valor in cambios.items():
            if c == codigo:
                row[encabezados.index(enc)].value = valor
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def zip_con(entradas: dict[str, bytes], metodo: int = zipfile.ZIP_DEFLATED) -> bytes:
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", metodo) as z:
        for nombre, datos in entradas.items():
            z.writestr(nombre, datos)
    return salida.getvalue()


def reemplazar_entrada(contenido: bytes, nombre: str, datos: bytes) -> bytes:
    original = zipfile.ZipFile(io.BytesIO(contenido))
    entradas = {n: original.read(n) for n in original.namelist()}
    entradas[nombre] = datos
    return zip_con(entradas)
