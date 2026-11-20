"""Importación y exportación del Excel de la planner (criterios de I-8; ADR 0009, 0018, 0026,
0028). Solo archivos FICTICIOS generados aquí (tests/planilla_ficticia.py); nunca el Excel real.
"""

import io
import zipfile

import openpyxl
import pytest
from sqlalchemy import text

from tests.db.test_auth_panel import NOVIA, PLANNER, Panel
from tests.db.test_panel_api import Actor
from tests.planilla_ficticia import (
    HOJA_NOVIA,
    HOJA_NOVIO,
    TIPO_XLSX,
    csv_planner,
    fila,
    libro,
    modificar,
    reemplazar_entrada,
    zip_con,
)

A = "/api/v1/admin"
MX52 = "+" + "52"  # se arma por partes (tests/test_sin_telefonos_reales.py)
T1, T2, T3 = "2025550101", "2025550102", "2025550103"  # serie 555-01XX, ficción

ENC_EXPORT = [
    "Código INV", "No.", "Nombre Invitado", "# Pases", "Teléfono/Celular",
    "Nombre Contacto Alterno", "Tel/Celular   de contacto alterno",
    "Infante (menor a 2 años no aplica asiento ni A&B)", "Adultos",
    "# de Niños (aplica asiento y alimentos)", "Invitado de", "¿Asistirá?",
    "Pases confirmados", "# de mesa", "Comentario", "Mensaje del invitado", "Grupo", "Rol",
    "Alergias",
]  # fmt: skip


@pytest.fixture
def panel(app_engine, reloj, limpiar) -> Panel:  # noqa: ANN001
    return Panel(app_engine, reloj)


@pytest.fixture
def novios(panel: Panel) -> Actor:
    return Actor(panel, NOVIA)


@pytest.fixture
def planner(panel: Panel) -> Actor:
    return Actor(panel, PLANNER)


def subir(actor: Actor, ruta: str, datos: bytes, tipo: str = TIPO_XLSX, **params):  # noqa: ANN003, ANN201
    cab = actor.sesion.escritura(**{"content-type": tipo})
    return actor.c.post(A + ruta, headers=cab, content=datos, params=params)


def vista(actor: Actor, datos: bytes, tipo: str = TIPO_XLSX, **params) -> dict:  # noqa: ANN003
    r = subir(actor, "/imports/preview", datos, tipo, **params)
    assert r.status_code == 200, r.text
    return r.json()


def aplicar(actor: Actor, datos: bytes, tipo: str = TIPO_XLSX, **params) -> dict:  # noqa: ANN003
    r = subir(actor, "/imports/apply", datos, tipo, **params)
    assert r.status_code == 200, r.text
    return r.json()


def exportar(actor: Actor, formato: str = "xlsx", solo_confirmados: bool = False):  # noqa: ANN201
    return actor.escribir(
        "POST", "/exports", {"formato": formato, "solo_confirmados": solo_confirmados}
    )


def celdas(contenido: bytes) -> list[list]:
    ws = openpyxl.load_workbook(io.BytesIO(contenido)).active
    return [[c.value for c in r] for r in ws.iter_rows()]


def instantanea(panel: Panel) -> dict:
    with panel.engine.connect() as c:
        return {
            t: [tuple(r) for r in c.execute(text(f"SELECT * FROM {t} ORDER BY 1, 2"))]
            for t in ("invitacion", "invitacion_rol", "version_respuesta", "enlace")
        }


def contar(panel: Panel, tabla: str) -> int:
    with panel.engine.connect() as c:
        return c.execute(text(f"SELECT count(*) FROM {tabla}")).scalar_one()


BASICAS = [
    fila(no_planner=1.0, nombre_mostrar="Familia Ficticia Uno", pases=2.0,
         telefono_principal=float(T1), adultos=2.0, ninos_autorizados=0.0, infantes=0.0),
    fila(no_planner=2.0, nombre_mostrar="Persona Ficticia + acompañante", pases=3.0,
         telefono_principal="202 555 0102", adultos=2.0, comentario="Llega tarde"),
    fila(no_planner=3.0, nombre_mostrar="Familia Ficticia Tres", pases=4.0, adultos=3.0,
         ninos_autorizados=1.0, infantes=1.0, comentario="Padrinos de lazo",
         contacto_alterno_nombre="Contacto Ficticio", contacto_alterno_tel=float(T3)),
    fila(no_planner=4.0, nombre_mostrar="Amigos Ficticios", pases=1.0, adultos=1.0,
         lado="Tía", telefono_principal="12345"),
]  # fmt: skip


# =========================================================================== hojas y estructura
def test_hoja_requerida_y_hojas_que_no_son_de_invitados(novios: Actor) -> None:
    datos = libro(BASICAS, BASICAS[:1])
    r = subir(novios, "/imports/preview", datos)
    assert r.status_code == 422 and r.json()["error"]["code"] == "hoja_requerida"
    assert r.json()["error"]["fields"]["hojas"] == [HOJA_NOVIO, HOJA_NOVIA]  # sin Presupuesto…
    v = vista(novios, datos, hoja=HOJA_NOVIA)
    assert v["hoja"] == HOJA_NOVIA and v["resumen"]["filas"] == 1
    r = subir(novios, "/imports/preview", datos, hoja="Presupuesto")
    assert r.json()["error"]["code"] == "hoja_no_encontrada"


def test_vista_previa_no_escribe_nada(novios: Actor, panel: Panel) -> None:
    antes = instantanea(panel)
    v = vista(novios, libro(BASICAS), lado_por_defecto="Novio")
    assert v["resumen"] | {"advertencia": None} == {
        "filas": 4, "altas": 4, "actualizaciones": 0, "sin_cambios": 0, "errores": 0,
        "en_revision": 2, "avisos": v["resumen"]["avisos"], "posibles_duplicados": 0,
        "advertencia": None,
    }  # fmt: skip
    assert instantanea(panel) == antes
    with panel.engine.connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM evento_auditoria WHERE accion = 'importacion'")
            ).scalar_one()
            == 0
        )  # noqa: E501


def test_altas_con_la_estructura_real(novios: Actor, panel: Panel) -> None:
    v = vista(novios, libro(BASICAS), lado_por_defecto="Novio")
    por_fila = {f["fila"]: f for f in v["filas"]}
    assert sorted(por_fila) == [
        3,
        4,
        5,
        6,
    ]  # datos desde la fila 3; las filas de formato se ignoran
    f2 = por_fila[4]
    assert f2["motivos_revision"] == ["pases_inconsistentes"]  # # Pases 3 ≠ 2 + 0
    aviso = next(a for a in f2["avisos"] if a["codigo"] == "nombre_con_varios")
    assert aviso["mensaje"] == (
        "Este nombre es el que verá el invitado («Invitación para …»). Conviene acortarlo "
        "antes de enviar enlaces."
    )
    assert por_fila[6]["motivos_revision"] == ["lado_invalido", "telefono_invalido"]
    assert {a["codigo"] for a in por_fila[6]["avisos"]} == {"sin_telefono"}
    r = aplicar(novios, libro(BASICAS), lado_por_defecto="Novio")
    assert r["resumen"]["altas"] == 4
    filas = {f["codigo"]: f for f in novios.get("/invitations").json()}
    assert sorted(filas) == ["INV-001", "INV-002", "INV-003", "INV-004"]
    uno, dos, tres, cuatro = (filas[f"INV-00{i}"] for i in range(1, 5))
    assert uno["telefono_principal"] == MX52 + T1 and uno["adultos"] == 2  # 2.0 → 2
    assert uno["lado"] == "Novio" and uno["no_planner"] == 1  # lado por defecto
    assert dos["telefono_principal"] == MX52 + T2 and dos["nota_interna"] == "Llega tarde"
    assert dos["nombre_mostrar"] == "Persona Ficticia + acompañante"  # tal cual
    assert dos["requiere_revision"] is True
    assert tres["roles"] == ["Padrinos de lazo"] and tres["nota_interna"] is None  # rol exacto
    assert tres["pases"] == 4 and tres["infantes"] == 1
    assert tres["contacto_alterno_tel"] == MX52 + T3
    assert cuatro["lado"] is None and cuatro["telefono_principal"] is None
    assert cuatro["motivos_revision"] == ["lado_invalido", "telefono_invalido"]
    detalle = novios.get("/invitations/INV-002").json()
    assert detalle["pases_planner_original"] == 3


def test_errores_de_fila_y_todo_o_nada(novios: Actor, panel: Panel) -> None:
    filas = [
        BASICAS[0],
        fila(nombre_mostrar="Sin Adultos Ficticia", pases=2.0),
        fila(nombre_mostrar="Adultos Decimal", adultos=2.5),
        fila(nombre_mostrar="Mesa Rara", adultos=1.0, mesa="la del fondo"),
        fila(adultos=2.0, telefono_principal=T2),  # sin nombre
        fila(nombre_mostrar="x" * 121, adultos=1.0),
    ]
    v = vista(novios, libro(filas))
    errores = [f["errores"] for f in v["filas"]]
    assert errores == [
        [], ["adultos_faltante"], ["adultos_invalido"], ["mesa_invalida"], ["nombre_faltante"],
        ["nombre_invalido"],
    ]  # fmt: skip
    assert v["resumen"]["errores"] == 5
    r = subir(novios, "/imports/apply", libro(filas))
    assert r.status_code == 409 and r.json()["error"]["code"] == "archivo_con_errores"
    assert contar(panel, "invitacion") == 0  # todo o nada


def test_columnas_faltantes(novios: Actor) -> None:
    datos = libro(BASICAS)
    wb = openpyxl.load_workbook(io.BytesIO(datos))
    wb[HOJA_NOVIO].cell(row=2, column=9, value="Mayores")  # renombra "Adultos"
    salida = io.BytesIO()
    wb.save(salida)
    r = subir(novios, "/imports/preview", salida.getvalue())
    assert r.status_code == 422 and r.json()["error"]["fields"] == {"columnas": ["Adultos"]}


def test_encabezado_con_espacios_distintos_se_reconoce(novios: Actor) -> None:
    wb = openpyxl.load_workbook(io.BytesIO(libro(BASICAS[:1])))
    wb[HOJA_NOVIO].cell(row=2, column=7, value="Tel/Celular de contacto alterno")  # 1 espacio
    salida = io.BytesIO()
    wb.save(salida)
    assert vista(novios, salida.getvalue())["resumen"]["altas"] == 1


def test_csv_con_punto_y_coma_y_windows_1252(novios: Actor) -> None:
    v = vista(novios, csv_planner(BASICAS), "text/csv", lado_por_defecto="Novia")
    assert v["formato"] == "csv" and v["resumen"]["altas"] == 4
    aplicar(novios, csv_planner(BASICAS), "text/csv", lado_por_defecto="Novia")
    uno = novios.get("/invitations/INV-001").json()
    assert uno["lado"] == "Novia" and uno["telefono_principal"] == MX52 + T1


# =========================================================================== duplicados y códigos
def test_reimportar_la_hoja_de_la_planner_avisa_duplicados(novios: Actor) -> None:
    aplicar(novios, libro(BASICAS))
    v = vista(novios, libro(BASICAS))
    assert v["resumen"]["posibles_duplicados"] == 4
    assert v["resumen"]["advertencia"].startswith("4 de 4 filas parecen ya importadas.")
    assert "reimportando el archivo exportado (con Código INV)" in v["resumen"]["advertencia"]
    # Dentro del mismo archivo también se avisa.
    v = vista(novios, libro([fila(nombre_mostrar="Repetida", adultos=1.0)] * 2))
    assert v["resumen"]["posibles_duplicados"] == 2 and v["resumen"]["altas"] == 2


def test_codigo_desconocido_invalido_y_archivada(novios: Actor) -> None:
    aplicar(novios, libro(BASICAS[:1]))
    novios.escribir("POST", "/invitations/INV-001/archive")
    filas = [
        fila(codigo="INV-999", nombre_mostrar="A", adultos=1.0),
        fila(codigo="X-1", nombre_mostrar="B", adultos=1.0),
        fila(codigo="INV-001", nombre_mostrar="C", adultos=1.0),
    ]
    v = vista(novios, libro(filas, extras=("codigo",)))
    assert [f["errores"] for f in v["filas"]] == [
        ["codigo_desconocido"], ["codigo_invalido"], ["archivada"],
    ]  # fmt: skip


def test_columna_rol_manda_sobre_comentario(novios: Actor) -> None:
    filas = [
        fila(
            nombre_mostrar="Uno", adultos=1.0, comentario="Padrinos de lazo", rol="Paje; Ofrendas"
        ),
        fila(nombre_mostrar="Dos", adultos=1.0, rol="Paje; Mago"),
        fila(nombre_mostrar="Tres", adultos=1.0, comentario="padrinos de lazo"),  # no exacto
    ]
    aplicar(novios, libro(filas, extras=("rol",)))
    uno = novios.get("/invitations/INV-001").json()
    assert uno["roles"] == ["Paje", "Ofrendas"] and uno["nota_interna"] == "Padrinos de lazo"
    dos = novios.get("/invitations/INV-002").json()
    assert dos["roles"] == ["Paje"] and dos["motivos_revision"] == ["rol_invalido"]
    aplicar(novios, libro([filas[2]]))
    tres = novios.get("/invitations/INV-004").json()
    assert tres["roles"] == [] and tres["nota_interna"] == "padrinos de lazo"


# =========================================================================== actualización
def test_actualiza_por_codigo_sin_tocar_respuestas(novios: Actor, panel: Panel) -> None:
    aplicar(novios, libro(BASICAS[:2]), lado_por_defecto="Novio")
    novios.escribir(
        "PUT",
        "/invitations/INV-001/response",
        {"asiste": True, "confirmados": 2, "alergias": "Nueces", "mensaje": "Ahí estaremos"},
    )
    respuestas = instantanea(panel)["version_respuesta"]
    exportado = exportar(novios).content
    cambiado = modificar(
        exportado,
        {
            ("INV-001", "# de mesa"): 5,
            ("INV-001", "¿Asistirá?"): "No",  # se ignora
            ("INV-001", "Alergias"): "Otra",  # se ignora
            ("INV-001", "Mensaje del invitado"): "Otro",  # se ignora
            ("INV-002", "Grupo"): "Amigos",
        },
    )
    v = vista(novios, cambiado)
    acciones = {f["codigo"]: (f["accion"], f["cambios"]) for f in v["filas"]}
    assert acciones == {
        "INV-001": ("actualizacion", ["mesa"]),
        "INV-002": ("actualizacion", ["grupo"]),
    }
    aplicar(novios, cambiado)
    assert novios.get("/invitations/INV-001").json()["mesa"] == 5
    assert novios.get("/invitations/INV-002").json()["grupo"] == "Amigos"
    assert instantanea(panel)["version_respuesta"] == respuestas  # respuestas intactas


def test_marca_de_revision_se_quita_al_corregir(novios: Actor) -> None:
    aplicar(novios, libro([BASICAS[1]]))  # # Pases 3 ≠ 2
    assert novios.get("/invitations/INV-001").json()["motivos_revision"] == ["pases_inconsistentes"]
    # "# Pases" se ignora en actualizaciones: corregir adultos quita la marca.
    cambiado = modificar(exportar(novios).content, {("INV-001", "Adultos"): 3})
    aplicar(novios, cambiado)
    d = novios.get("/invitations/INV-001").json()
    assert d["motivos_revision"] == [] and d["requiere_revision"] is False
    assert d["pases_planner_original"] == 3  # el original de la planner no cambia


def test_no_baja_pases_por_debajo_de_los_confirmados(novios: Actor) -> None:
    aplicar(novios, libro([BASICAS[2]]))  # 3 adultos + 1 niño
    novios.escribir("PUT", "/invitations/INV-001/response", {"asiste": True, "confirmados": 4})
    cambiado = modificar(exportar(novios).content, {("INV-001", "Adultos"): 1})
    v = vista(novios, cambiado)
    assert v["filas"][0]["errores"] == ["pases_menores_que_confirmados"]


def _datos_variados(novios: Actor, panel: Panel) -> None:
    aplicar(novios, libro(BASICAS), lado_por_defecto="Novio")
    novios.escribir(
        "PATCH",
        "/invitations/INV-001",
        {"grupo": "Familia", "roles": ["Paje", "Ofrendas"], "mesa": 3,
         "nota_interna": '=HYPERLINK("http://evil.invalid","x")'},
    )  # fmt: skip
    novios.escribir("PATCH", "/invitations/INV-003", {"nota_interna": "+ invitar al brindis"})
    novios.escribir(
        "PUT",
        "/invitations/INV-001/response",
        {"asiste": True, "confirmados": 2, "alergias": "Nueces", "mensaje": "-Saludos"},
    )
    novios.escribir("PUT", "/invitations/INV-002/response", {"asiste": False, "confirmados": 0})
    novios.escribir("POST", "/invitations/INV-003/link")
    novios.escribir("POST", "/invitations/INV-004/archive")


@pytest.mark.parametrize("formato", ["xlsx", "csv"])
def test_reimportar_el_archivo_exportado_no_cambia_nada(
    novios: Actor, panel: Panel, formato: str
) -> None:
    _datos_variados(novios, panel)
    antes = instantanea(panel)
    exportado = exportar(novios, formato).content
    tipo = TIPO_XLSX if formato == "xlsx" else "text/csv"
    r = aplicar(novios, exportado, tipo)
    assert r["resumen"]["actualizaciones"] == 0 and r["resumen"]["altas"] == 0
    assert r["resumen"]["sin_cambios"] == 3 and r["resumen"]["errores"] == 0
    assert instantanea(panel) == antes  # ni un byte distinto, ni actualizada_en


# =========================================================================== exportación
def test_exportacion_19_columnas_formatos_y_proteccion(novios: Actor, panel: Panel) -> None:
    _datos_variados(novios, panel)
    r = exportar(novios)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert r.headers["content-disposition"] == 'attachment; filename="invitados-2026-11-14.xlsx"'
    filas = celdas(r.content)
    assert filas[0] == ENC_EXPORT
    datos = {f[0]: dict(zip(ENC_EXPORT, f, strict=True)) for f in filas[1:]}
    assert sorted(datos) == ["INV-001", "INV-002", "INV-003"]  # sin archivadas
    uno, dos, tres = datos["INV-001"], datos["INV-002"], datos["INV-003"]
    assert uno["# Pases"] == 2 and uno["¿Asistirá?"] == "Sí" and uno["Pases confirmados"] == 2
    assert dos["¿Asistirá?"] == "No" and dos["Pases confirmados"] == 0
    assert dos["# Pases"] == 2  # calculado (el original era 3)
    assert tres["¿Asistirá?"] is None and tres["Pases confirmados"] is None  # pendiente
    assert uno["Teléfono/Celular"] == MX52 + T1  # E.164, sin neutralizar
    assert uno["Comentario"] == '\'=HYPERLINK("http://evil.invalid","x")'  # neutralizado
    assert uno["Mensaje del invitado"] == "'-Saludos"
    assert tres["Comentario"] == "'+ invitar al brindis"
    assert uno["Rol"] == "Paje; Ofrendas" and uno["Grupo"] == "Familia"
    assert uno["Alergias"] == "Nueces" and uno["Invitado de"] == "Novio"
    ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
    assert ws.auto_filter.ref == "A1:S4" and ws.freeze_panes == "A2"
    assert all(c.data_type != "f" for row in ws.iter_rows() for c in row)  # ninguna fórmula


def test_exportacion_sin_enlaces_ni_tokens(novios: Actor, planner: Actor) -> None:
    aplicar(novios, libro([BASICAS[0], BASICAS[2]]))  # sin filas en revisión
    url = lambda r: r.json()["url"].split("#t=")[1]  # noqa: E731
    tokens = [url(novios.escribir("POST", f"/invitations/INV-00{i}/link")) for i in (1, 2)]
    tokens.append(url(novios.escribir("POST", "/invitations/INV-001/link/regenerate")))
    for actor in (novios, planner):
        for formato in ("xlsx", "csv"):
            contenido = exportar(actor, formato).content
            texto = (
                contenido.decode("utf-8-sig")
                if formato == "csv"
                else "".join(
                    zipfile.ZipFile(io.BytesIO(contenido)).read(n).decode("utf-8", "replace")
                    for n in zipfile.ZipFile(io.BytesIO(contenido)).namelist()
                )
            )
            assert all(t not in texto for t in tokens) and "#t=" not in texto


def test_planner_exporta_lo_mismo_y_no_importa(novios: Actor, planner: Actor) -> None:
    _datos_variados(novios, novios.panel)
    assert celdas(exportar(planner).content) == celdas(exportar(novios).content)
    r = subir(planner, "/imports/preview", libro(BASICAS))
    assert r.status_code == 403 and r.json()["error"]["code"] == "sin_permiso"


def test_solo_confirmados_para_el_script_de_mayra(novios: Actor, panel: Panel) -> None:
    _datos_variados(novios, panel)
    r = exportar(novios, "xlsx", solo_confirmados=True)
    assert "invitados-confirmados-" in r.headers["content-disposition"]
    filas = celdas(r.content)
    assert [f[0] for f in filas[1:]] == ["INV-001"]
    assert filas[1][ENC_EXPORT.index("Teléfono/Celular")] == MX52 + T1


def test_csv_exportado_bom_y_neutralizado(novios: Actor, panel: Panel) -> None:
    _datos_variados(novios, panel)
    r = exportar(novios, "csv")
    assert r.content.startswith(b"\xef\xbb\xbf")
    texto = r.content.decode("utf-8-sig")
    assert texto.splitlines()[0].split(",")[0] == "Código INV"
    assert "'=HYPERLINK" in texto and "\n=HYPERLINK" not in texto and ",=" not in texto


def test_auditoria_de_importacion_y_exportacion_sin_datos(novios: Actor, panel: Panel) -> None:
    aplicar(novios, libro(BASICAS))
    exportar(novios, "csv", solo_confirmados=True)
    with panel.engine.connect() as c:
        eventos = {
            a: d
            for a, d in c.execute(
                text("SELECT accion, detalle FROM evento_auditoria WHERE accion IN "
                     "('importacion', 'exportacion')")
            )
        }  # fmt: skip
    assert eventos["importacion"] == {
        "formato": "xlsx", "filas": 4, "altas": 4, "actualizaciones": 0, "sin_cambios": 0,
        "en_revision": 2,
    }  # fmt: skip
    assert eventos["exportacion"] == {"formato": "csv", "filas": 0, "solo_confirmados": True}
    assert "Ficticia" not in str(eventos) and T1 not in str(eventos)


# =========================================================================== archivos maliciosos
def _bomba() -> bytes:
    """Un libro VÁLIDO con una entrada extra que se infla ~1000 veces: solo el control de
    proporción puede rechazarlo (openpyxl ignoraría la entrada)."""
    ceros = b"\x00" * (25 * 1024 * 1024)  # 25 MB que se comprimen a unos KB
    return reemplazar_entrada(libro(BASICAS[:1]), "xl/media/relleno.bin", ceros)


ENTIDADES = (
    b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
    b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]>'
    b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="1" '
    b'uniqueCount="1"><si><t>&lol2;</t></si></sst>'
)


@pytest.mark.parametrize(
    ("caso", "datos", "tipo", "status", "codigo"),
    [
        ("demasiado grande", b"PK\x03\x04" + b"0" * (2 * 1024 * 1024), TIPO_XLSX, 413,
         "cuerpo_demasiado_grande"),
        ("bomba zip", None, TIPO_XLSX, 415, "archivo_no_valido"),
        ("demasiadas entradas", "muchas", TIPO_XLSX, 415, "archivo_no_valido"),
        ("macros", "macros", TIPO_XLSX, 415, "formato_no_soportado"),
        ("ruta con ..", "ruta", TIPO_XLSX, 415, "archivo_no_valido"),
        ("xls antiguo", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100, TIPO_XLSX, 415,
         "formato_no_soportado"),
        ("zip sin libro", "sin_libro", TIPO_XLSX, 415, "formato_no_soportado"),
        ("basura", b"PK\x03\x04basura", TIPO_XLSX, 415, "archivo_no_valido"),
        ("binario como csv", b"\x00\x01\x02", "text/csv", 415, "formato_no_soportado"),
        ("entidades xml", "entidades", TIPO_XLSX, 415, "archivo_no_valido"),
        ("vacío", b"", TIPO_XLSX, 415, "archivo_no_valido"),
    ],
)  # fmt: skip
def test_archivos_maliciosos(  # noqa: PLR0913
    novios: Actor,
    caso: str,
    datos,
    tipo: str,
    status: int,
    codigo: str,  # noqa: ANN001
) -> None:
    base = libro(BASICAS[:1])
    datos = {
        None: _bomba() if datos is None else None,
        "muchas": zip_con({"xl/workbook.xml": b"<x/>", **{f"x/{i}": b"a" for i in range(300)}}),
        "macros": reemplazar_entrada(base, "xl/vbaProject.bin", b"\x00" * 10),
        "ruta": zip_con({"xl/workbook.xml": b"<x/>", "../malo.txt": b"x"}),
        "sin_libro": zip_con({"hola.txt": b"x"}),
        "entidades": reemplazar_entrada(base, "xl/sharedStrings.xml", ENTIDADES),
    }.get(datos, datos)
    r = subir(novios, "/imports/preview", datos, tipo)
    assert r.status_code == status, (caso, r.status_code, r.text[:200])
    assert r.json()["error"]["code"] == codigo
