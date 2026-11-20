"""Lectura segura de los archivos de importación (I-8; ADR 0019, 0028).

- Solo .xlsx y .csv. El tipo se decide por la firma del archivo, no solo por el Content-Type.
- Antes de abrir un .xlsx se revisa el ZIP: número de entradas, tamaño descomprimido total,
  proporción de compresión (bomba ZIP), entradas cifradas, macros y rutas peligrosas.
  `zipfile` nunca lee más bytes de los que declara cada entrada (y verifica su CRC), así que los
  tamaños declarados acotan lo que se descomprime.
- openpyxl abre en modo solo lectura, sin evaluar fórmulas ni seguir vínculos externos, y usa
  defusedxml (instalado) contra entidades externas y expansiones de XML.
- Se leen como máximo `MAX_FILAS` filas y `MAX_COLUMNAS` columnas por hoja.
- Ningún error incluye contenido del archivo.
"""

import csv
import io
import zipfile
from dataclasses import dataclass

from app.errores import ErrorAPI

MAX_ENTRADAS_ZIP = 200
MAX_DESCOMPRIMIDO = 30 * 1024 * 1024
MAX_PROPORCION = 200  # descomprimido / comprimido, para entradas de más de 1 MB
MAX_FILAS = 5000
MAX_COLUMNAS = 30
FILAS_BUSQUEDA_ENCABEZADO = 10
FIRMA_ZIP = b"PK\x03\x04"
FIRMA_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # .xls antiguo


@dataclass
class Hoja:
    nombre: str
    filas: list[list[object]]  # valores crudos; la fila 0 es la fila 1 del archivo


def _no_soportado() -> ErrorAPI:
    return ErrorAPI(415, "formato_no_soportado")


def _no_valido() -> ErrorAPI:
    return ErrorAPI(415, "archivo_no_valido")


def formato(datos: bytes, content_type: str | None) -> str:
    """'xlsx' o 'csv' según la firma. .xls, .xlsm y binarios → 415."""
    if not datos:
        raise _no_valido()
    if datos.startswith(FIRMA_ZIP):
        return "xlsx"
    if datos.startswith(FIRMA_OLE):
        raise _no_soportado()
    tipo = (content_type or "").split(";")[0].strip().lower()
    if tipo in ("text/csv", "application/csv", "text/plain") and b"\x00" not in datos[:4096]:
        return "csv"
    raise _no_soportado()


def revisar_zip(datos: bytes) -> None:
    try:
        z = zipfile.ZipFile(io.BytesIO(datos))
    except (zipfile.BadZipFile, ValueError):
        raise _no_valido() from None
    infos = z.infolist()
    if not infos or len(infos) > MAX_ENTRADAS_ZIP:
        raise _no_valido()
    total = 0
    nombres = set()
    for i in infos:
        nombre = i.filename.replace("\\", "/")
        if nombre.startswith("/") or ".." in nombre.split("/") or ":" in nombre:
            raise _no_valido()
        if i.flag_bits & 0x1:  # cifrada
            raise _no_valido()
        if nombre.lower().endswith("vbaproject.bin"):  # macros (.xlsm disfrazado)
            raise _no_soportado()
        total += i.file_size
        if total > MAX_DESCOMPRIMIDO:
            raise _no_valido()
        if i.file_size > 1024 * 1024 and i.file_size > MAX_PROPORCION * max(i.compress_size, 1):
            raise _no_valido()
        nombres.add(nombre)
    if "xl/workbook.xml" not in nombres:
        raise _no_soportado()
    # Un .xlsx legítimo nunca declara DTD ni entidades: se rechaza cualquier XML que las traiga
    # (openpyxl no usa defusedxml en todos sus lectores). Los tamaños ya están acotados arriba.
    for i in infos:
        if i.filename.lower().endswith((".xml", ".rels", ".vml")):
            contenido = z.read(i).lower()
            if b"<!doctype" in contenido or b"<!entity" in contenido:
                raise _no_valido()


def _celdas(fila: tuple) -> list[object]:
    return list(fila[:MAX_COLUMNAS])


def leer_xlsx(datos: bytes, es_candidata) -> list[Hoja]:  # noqa: ANN001
    """Hojas candidatas (según `es_candidata(primeras_filas)`) con sus filas. Las demás hojas
    solo se miran en sus primeras filas para descartarlas."""
    import openpyxl

    revisar_zip(datos)
    try:
        libro = openpyxl.load_workbook(
            io.BytesIO(datos), read_only=True, data_only=True, keep_links=False
        )
    except Exception:  # noqa: BLE001 (cualquier fallo de formato es "archivo no válido")
        raise _no_valido() from None
    hojas = []
    try:
        for ws in libro.worksheets:
            primeras = [
                _celdas(f)
                for f in ws.iter_rows(
                    min_row=1, max_row=FILAS_BUSQUEDA_ENCABEZADO, max_col=MAX_COLUMNAS,
                    values_only=True,
                )
            ]  # fmt: skip
            if not es_candidata(primeras):
                continue
            filas = [
                _celdas(f)
                for f in ws.iter_rows(
                    min_row=1, max_row=MAX_FILAS, max_col=MAX_COLUMNAS, values_only=True
                )
            ]
            hojas.append(Hoja(ws.title, filas))
    except Exception:  # noqa: BLE001
        raise _no_valido() from None
    finally:
        libro.close()
    return hojas


def leer_csv(datos: bytes) -> list[Hoja]:
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            texto = datos.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover (cp1252 decodifica casi todo)
        raise _no_valido()
    # Separador más frecuente en las primeras líneas (Excel en español suele usar ";").
    muestra = texto[:8192].splitlines()[:20]
    separador = max(",;\t", key=lambda d: sum(linea.count(d) for linea in muestra))
    lector = csv.reader(io.StringIO(texto), delimiter=separador)
    filas = []
    try:
        for i, fila in enumerate(lector):
            if i >= MAX_FILAS:
                break
            filas.append([c if c != "" else None for c in fila[:MAX_COLUMNAS]])
    except csv.Error:
        raise _no_valido() from None
    return [Hoja("CSV", filas)]
