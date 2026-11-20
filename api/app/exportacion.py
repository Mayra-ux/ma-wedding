"""Exportación .xlsx / .csv para novios y planner (I-8; ADR 0009, 0018, 0026, 0028).

- 19 columnas en orden: Código INV + las 14 de la planner (encabezados reales) + Mensaje del
  invitado, Grupo, Rol, Alergias. Iguales para los dos roles. Sin archivadas.
- Nunca lleva enlaces ni tokens.
- Protección contra fórmulas: una celda de texto que empieza con =, +, -, @, tabulador o
  retorno se escribe con ' delante (la importación lo quita). Excepción: los teléfonos E.164
  que genera la propia API, ya validados.
- Teléfonos en E.164 como texto; autofiltro y fila de encabezados fija (script del día de la
  boda: filtrar ¿Asistirá? = Sí, o pedir `solo_confirmados`).
"""

import csv
import io
import re
from datetime import date

from app.planilla import ENCABEZADOS, EXTRAS

COLUMNAS = [
    ("codigo", EXTRAS["codigo"]),
    *ENCABEZADOS.items(),
    ("mensaje", EXTRAS["mensaje"]),
    ("grupo", EXTRAS["grupo"]),
    ("rol", EXTRAS["rol"]),
    ("alergias", EXTRAS["alergias"]),
]
TELEFONOS = {"telefono_principal", "contacto_alterno_tel"}
_E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")
_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")
TIPOS = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
}


def neutralizar(clave: str, valor: object) -> object:
    if not isinstance(valor, str) or not valor:
        return valor
    if clave in TELEFONOS and _E164.fullmatch(valor):
        return valor
    return "'" + valor if valor.startswith(_PELIGROSOS) else valor


def _valores(f: dict) -> dict:
    estado = f["estado_respuesta"]
    return {
        "codigo": f["codigo"],
        "no_planner": f["no_planner"],
        "nombre_mostrar": f["nombre_mostrar"],
        "pases": f["pases"],  # calculado (ADR 0018)
        "telefono_principal": f["telefono_principal"],
        "contacto_alterno_nombre": f["contacto_alterno_nombre"],
        "contacto_alterno_tel": f["contacto_alterno_tel"],
        "infantes": f["infantes"],
        "adultos": f["adultos"],
        "ninos_autorizados": f["ninos_autorizados"],
        "lado": f["lado"],
        "asistira": {"confirmada": "Sí", "no_asiste": "No"}.get(estado),
        "pases_confirmados": None if estado == "pendiente" else f["confirmados"],
        "mesa": f["mesa"],
        "comentario": f["nota_interna"],
        "mensaje": f["mensaje"],
        "grupo": f["grupo"],
        "rol": "; ".join(f["roles"]) or None,
        "alergias": f["alergias"],
    }


def filas_exportacion(filas: list[dict], solo_confirmados: bool) -> list[list[object]]:
    salida = []
    for f in filas:
        if f["archivada"] or (solo_confirmados and f["estado_respuesta"] != "confirmada"):
            continue
        v = _valores(f)
        salida.append([neutralizar(k, v[k]) for k, _ in COLUMNAS])
    return salida


def a_xlsx(filas: list[list[object]]) -> bytes:
    import openpyxl

    libro = openpyxl.Workbook()
    ws = libro.active
    ws.title = "Lista de invitados"
    ws.append([enc for _, enc in COLUMNAS])
    for fila in filas:
        ws.append(fila)
    for col in ws.iter_cols(min_row=2):
        for celda in col:
            if isinstance(celda.value, str):
                celda.data_type = "s"  # texto explícito, nunca fórmula
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, (_, enc) in enumerate(COLUMNAS, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = min(max(len(enc), 10), 40)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def a_csv(filas: list[list[object]]) -> bytes:
    texto = io.StringIO()
    escritor = csv.writer(texto, lineterminator="\r\n")
    escritor.writerow([enc for _, enc in COLUMNAS])
    for fila in filas:
        escritor.writerow(["" if v is None else v for v in fila])
    return texto.getvalue().encode("utf-8-sig")  # BOM: Excel lo abre como UTF-8


def nombre_archivo(formato: str, hoy: date, solo_confirmados: bool) -> str:
    sufijo = "-confirmados" if solo_confirmados else ""
    return f"invitados{sufijo}-{hoy.isoformat()}.{formato}"
