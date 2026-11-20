"""Importación del Excel/CSV de la planner (I-8; ADR 0009, 0018, 0026, 0028).

Vista previa y aplicación usan el mismo análisis (`analizar`). La vista previa no escribe nada;
aplicar repite el análisis dentro de una transacción con las invitaciones bloqueadas y, si hay
cualquier error de fila, no escribe nada (todo o nada).

Reglas principales:
- Columnas por su encabezado (ver ENCABEZADOS); la fila de encabezados se busca en las primeras
  10 filas, así que el título de la fila 1 y la columna A vacía no estorban.
- Con Código INV existente se actualiza; sin código se da de alta; código desconocido o de una
  invitación archivada es error de fila. Lo que no viene en el archivo no se borra.
- "# Pases" solo cuenta en las altas (original de la planner); en actualizaciones se ignora.
- Se ignoran ¿Asistirá?, Pases confirmados, Mensaje del invitado y Alergias: las respuestas
  nunca cambian por importación.
- "Comentario": con columna Rol es siempre nota; sin ella, es rol solo si coincide exacto.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.archivos import Hoja, formato, leer_csv, leer_xlsx
from app.catalogos import GRUPOS, LADOS, MOTIVOS_REVISION, ROLES_BODA
from app.errores import ErrorAPI
from app.invitaciones import _siguiente_codigo, auditar, normalizar_telefono
from app.models import Enlace, Invitacion, InvitacionRol, VersionRespuesta

# Encabezados exactos del archivo real de la planner (columnas B a O), ADR 0028.
ENCABEZADOS = {
    "no_planner": "No.",
    "nombre_mostrar": "Nombre Invitado",
    "pases": "# Pases",
    "telefono_principal": "Teléfono/Celular",
    "contacto_alterno_nombre": "Nombre Contacto Alterno",
    "contacto_alterno_tel": "Tel/Celular   de contacto alterno",
    "infantes": "Infante (menor a 2 años no aplica asiento ni A&B)",
    "adultos": "Adultos",
    "ninos_autorizados": "# de Niños (aplica asiento y alimentos)",
    "lado": "Invitado de",
    "asistira": "¿Asistirá?",
    "pases_confirmados": "Pases confirmados",
    "mesa": "# de mesa",
    "comentario": "Comentario",
}
EXTRAS = {
    "codigo": "Código INV",
    "mensaje": "Mensaje del invitado",
    "grupo": "Grupo",
    "rol": "Rol",
    "alergias": "Alergias",
}
MAX_NOMBRE, MAX_NOTA, MAX_CONTACTO, MAX_FILAS_DATOS = 120, 500, 120, 1000
_CODIGO = re.compile(r"^INV-[0-9]{3,}$")
_NEUTRALIZADOS = ("=", "+", "-", "@", "\t", "\r")

AVISOS = {
    "nombre_con_varios": (
        "Este nombre es el que verá el invitado («Invitación para …»). Conviene acortarlo "
        "antes de enviar enlaces."
    ),
    "posible_duplicado": "Ya existe una invitación o una fila con este mismo nombre.",
    "sin_telefono": "La invitación no tiene teléfono principal.",
    "enlace_activo_en_revision": (
        "Queda en revisión con su enlace activo: el enlace sigue funcionando (D7)."
    ),
}
ADVERTENCIA_DUPLICADOS = (
    "{n} de {total} filas parecen ya importadas. Cada hoja de la planner se importa una vez; "
    "después, los cambios se hacen en el panel o reimportando el archivo exportado "
    "(con Código INV)."
)


def normalizar_encabezado(valor: object) -> str:
    return " ".join(str(valor).split()) if valor is not None else ""


_REQUERIDOS = {normalizar_encabezado(v): k for k, v in ENCABEZADOS.items()}
_OPCIONALES = {normalizar_encabezado(v): k for k, v in EXTRAS.items()}


def _fila_encabezados(filas: list[list[object]]) -> int | None:
    objetivo = normalizar_encabezado(ENCABEZADOS["nombre_mostrar"])
    for i, fila in enumerate(filas[:10]):
        if any(normalizar_encabezado(c) == objetivo for c in fila):
            return i
    return None


def es_hoja_de_invitados(primeras: list[list[object]]) -> bool:
    return _fila_encabezados(primeras) is not None


# --------------------------------------------------------------------------- celdas
class _ErrorCelda(Exception):
    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo


def _texto(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).replace("\r\n", "\n").strip()
    # Deshace la neutralización de fórmulas de la exportación ('=…, '+…).
    if len(s) > 1 and s[0] == "'" and s[1] in _NEUTRALIZADOS:
        s = s[1:]
    return s or None


def _texto_valido(v: object, maximo: int, error: str) -> str | None:
    s = _texto(v)
    if s is None:
        return None
    if any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in s):
        raise _ErrorCelda(error)
    if len(s) > maximo:
        raise _ErrorCelda(error)
    return s


def _entero(v: object, error: str) -> int | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        raise _ErrorCelda(error)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if v.is_integer():
            return int(v)
        raise _ErrorCelda(error)
    s = str(v).strip()
    if re.fullmatch(r"-?[0-9]+(\.0+)?", s):
        return int(float(s))
    raise _ErrorCelda(error)


def _telefono(v: object) -> tuple[str | None, bool]:
    """(teléfono normalizado o None, es_invalido). Vacío no es inválido."""
    if isinstance(v, float) and v.is_integer():
        v = str(int(v))
    elif isinstance(v, int):
        v = str(v)
    s = _texto(v)
    if s is None:
        return None, False
    if re.fullmatch(r"[0-9]+\.0+", s):  # número leído como texto (CSV): 4441234567.0
        s = s.split(".")[0]
    try:
        return normalizar_telefono(s, "telefono"), False
    except ErrorAPI:
        return None, True


def _clave_nombre(nombre: str) -> str:
    return " ".join(nombre.casefold().split())


# --------------------------------------------------------------------------- análisis
@dataclass
class Fila:
    fila: int  # número de fila en el archivo (1 = primera)
    codigo: str | None = None
    nombre: str | None = None
    datos: dict = field(default_factory=dict)  # campos de la invitación
    roles: list[str] | None = None  # None: la fila no define roles
    grupo_definido: bool = False
    pases_archivo: int | None = None
    invalidos: dict[str, bool | None] = field(default_factory=dict)  # motivo → inválido/válido/None
    errores: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    accion: str = "alta"
    cambios: list[str] = field(default_factory=list)
    motivos: list[str] = field(default_factory=list)


@dataclass
class Analisis:
    formato: str
    hoja: str
    hojas: list[str]
    filas: list[Fila]
    columnas_desconocidas: list[str]
    no_incluidas: list[str]

    def resumen(self) -> dict:
        c = lambda a: sum(1 for f in self.filas if f.accion == a)  # noqa: E731
        duplicados = sum(1 for f in self.filas if "posible_duplicado" in f.avisos)
        r = {
            "filas": len(self.filas),
            "altas": c("alta"),
            "actualizaciones": c("actualizacion"),
            "sin_cambios": c("sin_cambios"),
            "errores": c("error"),
            "en_revision": sum(1 for f in self.filas if f.accion != "error" and f.motivos),
            "avisos": sum(len(f.avisos) for f in self.filas),
            "posibles_duplicados": duplicados,
            "advertencia": (
                ADVERTENCIA_DUPLICADOS.format(n=duplicados, total=len(self.filas))
                if duplicados
                else None
            ),
        }
        return r

    def respuesta(self) -> dict:
        return {
            "formato": self.formato,
            "hoja": self.hoja,
            "hojas_disponibles": self.hojas,
            "resumen": self.resumen(),
            "columnas_desconocidas": self.columnas_desconocidas,
            "filas": [
                {
                    "fila": f.fila,
                    "codigo": f.codigo,
                    "nombre": f.nombre,
                    "accion": f.accion,
                    "cambios": f.cambios,
                    "errores": f.errores,
                    "motivos_revision": f.motivos,
                    "avisos": [{"codigo": a, "mensaje": AVISOS[a]} for a in f.avisos],
                }
                for f in self.filas
            ],
            "no_incluidas": self.no_incluidas,
        }


def _leer(datos: bytes, content_type: str | None, hoja: str | None) -> tuple[str, Hoja, list]:
    fmt = formato(datos, content_type)
    hojas = leer_xlsx(datos, es_hoja_de_invitados) if fmt == "xlsx" else leer_csv(datos)
    nombres = [h.nombre for h in hojas]
    if fmt == "csv":
        return fmt, hojas[0], nombres
    if not hojas:
        raise ErrorAPI(422, "columnas_faltantes", {"columnas": [ENCABEZADOS["nombre_mostrar"]]})
    if hoja is None:
        if len(hojas) > 1:
            raise ErrorAPI(422, "hoja_requerida", {"hojas": nombres})
        return fmt, hojas[0], nombres
    for h in hojas:
        if h.nombre == hoja:
            return fmt, h, nombres
    raise ErrorAPI(422, "hoja_no_encontrada", {"hojas": nombres})


def _parsear_fila(n: int, fila: list[object], cols: dict[str, int], lado_defecto: str | None):
    def celda(clave: str) -> object:
        i = cols.get(clave)
        return fila[i] if i is not None and i < len(fila) else None

    claves = [k for k in cols if k not in ("asistira", "pases_confirmados", "mensaje", "alergias")]
    if all(_texto(celda(k)) is None for k in claves):
        return None  # fila vacía (de formato)
    f = Fila(fila=n)

    def intentar(funcion, *args):  # noqa: ANN001, ANN002, ANN202
        try:
            return funcion(*args)
        except _ErrorCelda as exc:
            f.errores.append(exc.codigo)
            return None

    if "codigo" in cols:
        codigo = _texto(celda("codigo"))
        if codigo is not None and not _CODIGO.fullmatch(codigo):
            f.errores.append("codigo_invalido")
        f.codigo = codigo
    f.nombre = intentar(_texto_valido, celda("nombre_mostrar"), MAX_NOMBRE, "nombre_invalido")
    if f.nombre is None and "nombre_invalido" not in f.errores:
        f.errores.append("nombre_faltante")
    adultos = intentar(_entero, celda("adultos"), "adultos_invalido")
    if adultos is None and "adultos_invalido" not in f.errores:
        f.errores.append("adultos_faltante")
    elif adultos is not None and adultos < 1:
        f.errores.append("adultos_invalido")
    ninos = intentar(_entero, celda("ninos_autorizados"), "ninos_invalido") or 0
    infantes = intentar(_entero, celda("infantes"), "infantes_invalido") or 0
    if ninos < 0:
        f.errores.append("ninos_invalido")
    if infantes < 0:
        f.errores.append("infantes_invalido")
    f.pases_archivo = intentar(_entero, celda("pases"), "pases_invalido")
    mesa = intentar(_entero, celda("mesa"), "mesa_invalida")
    if mesa is not None and mesa < 1:
        f.errores.append("mesa_invalida")
    no_planner = intentar(_entero, celda("no_planner"), "no_invalido")
    if no_planner is not None and no_planner < 1:
        f.errores.append("no_invalido")
    alterno_nombre = intentar(
        _texto_valido, celda("contacto_alterno_nombre"), MAX_CONTACTO, "contacto_invalido"
    )
    comentario = intentar(_texto_valido, celda("comentario"), MAX_NOTA, "comentario_invalido")

    # Lado: vacío → lado por defecto elegido al importar; valor no reconocido → revisión.
    lado_txt = _texto(celda("lado"))
    lado = lado_txt if lado_txt is not None else lado_defecto
    f.invalidos["lado_invalido"] = None if lado_txt is None else lado_txt not in LADOS
    if lado is not None and lado not in LADOS:
        lado = None
    tel, tel_malo = _telefono(celda("telefono_principal"))
    tel2, tel2_malo = _telefono(celda("contacto_alterno_tel"))
    llenos = [_texto(celda(k)) is not None for k in ("telefono_principal", "contacto_alterno_tel")]
    # Inválido si alguno lo es; válido solo si los dos vienen llenos y válidos; si no, se conserva
    # el motivo (así reimportar el archivo exportado no cambia nada).
    f.invalidos["telefono_invalido"] = (
        True if (tel_malo or tel2_malo) else (False if all(llenos) else None)
    )

    nota = comentario
    if "rol" in cols:
        texto_rol = _texto(celda("rol"))
        if texto_rol is None:
            f.roles = []
            f.invalidos["rol_invalido"] = None
        else:
            partes = [p.strip() for p in texto_rol.split(";") if p.strip()]
            validos = [p for p in partes if p in ROLES_BODA]
            f.roles = sorted(set(validos), key=ROLES_BODA.index)
            f.invalidos["rol_invalido"] = len(validos) != len(partes)
    elif comentario is not None and comentario in ROLES_BODA:
        f.roles, nota = [comentario], None  # coincidencia exacta con el catálogo (ADR 0018)
    if "grupo" in cols:
        f.grupo_definido = True
        grupo = _texto(celda("grupo"))
        f.invalidos["grupo_invalido"] = None if grupo is None else grupo not in GRUPOS
        f.datos["grupo"] = grupo if grupo in GRUPOS else None

    f.datos.update(
        nombre_mostrar=f.nombre,
        adultos=adultos,
        ninos_autorizados=ninos,
        infantes=infantes,
        lado=lado,
        mesa=mesa,
        nota_interna=nota,
        no_planner=no_planner,
        telefono_principal=tel,
        contacto_alterno_nombre=alterno_nombre,
        contacto_alterno_tel=tel2,
    )
    if f.nombre is not None and "+" in f.nombre:
        f.avisos.append("nombre_con_varios")
    if tel is None:
        f.avisos.append("sin_telefono")
    return f


def _motivos(base: set[str], f: Fila, original: int | None, pases: int) -> list[str]:
    """Motivos resultantes: inválido → se agrega; válido → se quita; vacío → se conserva."""
    motivos = set(base)
    if original is not None and original != pases:
        motivos.add("pases_inconsistentes")
    else:
        motivos.discard("pases_inconsistentes")
    for motivo, invalido in f.invalidos.items():
        if invalido is True:
            motivos.add(motivo)
        elif invalido is False:
            motivos.discard(motivo)
    return sorted(motivos, key=MOTIVOS_REVISION.index)


def analizar(
    s: Session,
    datos: bytes,
    content_type: str | None,
    hoja: str | None,
    lado_defecto: str | None,
    *,
    bloquear: bool = False,
) -> Analisis:
    if lado_defecto is not None and lado_defecto not in LADOS:
        raise ErrorAPI(422, "validacion", {"lado_por_defecto": "fuera_de_catalogo"})
    fmt, h, nombres = _leer(datos, content_type, hoja)
    i_enc = _fila_encabezados(h.filas)
    if i_enc is None:
        raise ErrorAPI(422, "columnas_faltantes", {"columnas": list(ENCABEZADOS.values())})
    cols: dict[str, int] = {}
    desconocidas = []
    for j, valor in enumerate(h.filas[i_enc]):
        enc = normalizar_encabezado(valor)
        if not enc:
            continue
        clave = _REQUERIDOS.get(enc) or _OPCIONALES.get(enc)
        if clave is None:
            desconocidas.append(enc)
        elif clave not in cols:
            cols[clave] = j
    faltantes = [ENCABEZADOS[k] for k in ENCABEZADOS if k not in cols]
    if faltantes:
        raise ErrorAPI(422, "columnas_faltantes", {"columnas": faltantes})

    filas = []
    for n, fila in enumerate(h.filas[i_enc + 1 :], start=i_enc + 2):
        f = _parsear_fila(n, fila, cols, lado_defecto)
        if f is not None:
            filas.append(f)
    if len(filas) > MAX_FILAS_DATOS:
        raise ErrorAPI(422, "validacion", {"filas": "demasiadas"})

    # --- comparación con la base
    codigos = {f.codigo for f in filas if f.codigo and _CODIGO.fullmatch(f.codigo)}
    consulta = select(Invitacion).where(Invitacion.codigo.in_(codigos)).order_by(Invitacion.id)
    if bloquear:
        consulta = consulta.with_for_update()
    existentes = {
        i.codigo: i for i in s.scalars(consulta.execution_options(populate_existing=True))
    }
    ids = [i.id for i in existentes.values()]
    vigentes = {
        v.invitacion_id: v.confirmados
        for v in s.scalars(
            select(VersionRespuesta).where(
                VersionRespuesta.vigente, VersionRespuesta.invitacion_id.in_(ids)
            )
        )
    }
    roles_actuales: dict[int, list[str]] = {}
    for r in s.scalars(select(InvitacionRol).where(InvitacionRol.invitacion_id.in_(ids))):
        roles_actuales.setdefault(r.invitacion_id, []).append(r.rol)
    con_enlace = set(
        s.scalars(
            select(Enlace.invitacion_id).where(
                Enlace.revocado_en.is_(None), Enlace.invitacion_id.in_(ids)
            )
        )
    )
    nombres_bd = {
        _clave_nombre(n) for n in s.scalars(select(Invitacion.nombre_mostrar)) if n is not None
    }
    vistos: dict[str, int] = {}
    for f in filas:
        if f.nombre:
            vistos[_clave_nombre(f.nombre)] = vistos.get(_clave_nombre(f.nombre), 0) + 1

    for f in filas:
        if f.codigo and not f.errores:
            inv = existentes.get(f.codigo)
            if inv is None:
                f.errores.append("codigo_desconocido")
            elif inv.archivada_en is not None:
                f.errores.append("archivada")
        if f.errores:
            f.accion = "error"
            continue
        pases = f.datos["adultos"] + f.datos["ninos_autorizados"]
        if f.codigo:  # actualización
            inv = existentes[f.codigo]
            if vigentes.get(inv.id, 0) > pases:
                f.errores.append("pases_menores_que_confirmados")
                f.accion = "error"
                continue
            f.motivos = _motivos(
                set(inv.motivos_revision or []), f, inv.pases_planner_original, pases
            )
            actuales = sorted(roles_actuales.get(inv.id, []), key=ROLES_BODA.index)
            f.cambios = [k for k, v in f.datos.items() if getattr(inv, k) != v]
            if f.roles is not None and f.roles != actuales:
                f.cambios.append("roles")
            if f.motivos != list(inv.motivos_revision or []):
                f.cambios.append("motivos_revision")
            f.accion = "actualizacion" if f.cambios else "sin_cambios"
            if f.motivos and inv.id in con_enlace:
                f.avisos.append("enlace_activo_en_revision")
        else:  # alta
            f.motivos = _motivos(set(), f, f.pases_archivo, pases)
            clave = _clave_nombre(f.nombre)
            if clave in nombres_bd or vistos.get(clave, 0) > 1:
                f.avisos.append("posible_duplicado")
    activos = s.scalars(select(Invitacion.codigo).where(Invitacion.archivada_en.is_(None))).all()
    presentes = {f.codigo for f in filas if f.codigo}
    no_incluidas = sorted((c for c in activos if c not in presentes), key=lambda c: int(c[4:]))
    return Analisis(fmt, h.nombre, nombres, filas, desconocidas, no_incluidas)


# --------------------------------------------------------------------------- aplicar
def aplicar(
    s: Session,
    datos: bytes,
    content_type: str | None,
    hoja: str | None,
    lado_defecto: str | None,
    actor: str,
) -> Analisis:
    a = analizar(s, datos, content_type, hoja, lado_defecto, bloquear=True)
    if any(f.accion == "error" for f in a.filas):
        raise ErrorAPI(409, "archivo_con_errores", {"resumen": a.resumen()})
    for f in a.filas:
        if f.accion == "alta":
            f.codigo = _alta(s, f)
        elif f.accion == "actualizacion":
            _actualizar(s, f)
    s.flush()
    r = a.resumen()
    auditar(
        s,
        actor,
        "importacion",
        detalle={
            "formato": a.formato,
            "filas": r["filas"],
            "altas": r["altas"],
            "actualizaciones": r["actualizaciones"],
            "sin_cambios": r["sin_cambios"],
            "en_revision": r["en_revision"],
        },
    )
    return a


def _alta(s: Session, f: Fila) -> str:
    campos = dict(f.datos)
    campos.update(
        pases_planner_original=f.pases_archivo,
        motivos_revision=f.motivos,
        requiere_revision=bool(f.motivos),
    )
    for _intento in range(5):
        codigo = _siguiente_codigo(s)
        try:
            with s.begin_nested():
                inv = Invitacion(codigo=codigo, **campos)
                s.add(inv)
                s.flush()
        except IntegrityError:
            continue
        s.add_all(InvitacionRol(invitacion_id=inv.id, rol=r) for r in (f.roles or []))
        return codigo
    raise ErrorAPI(409, "conflicto_codigo")


def _actualizar(s: Session, f: Fila) -> None:
    inv = s.scalar(select(Invitacion).where(Invitacion.codigo == f.codigo))
    for k, v in f.datos.items():
        setattr(inv, k, v)
    inv.motivos_revision = f.motivos
    inv.requiere_revision = bool(f.motivos)
    if f.roles is not None and "roles" in f.cambios:
        s.execute(delete(InvitacionRol).where(InvitacionRol.invitacion_id == inv.id))
        s.add_all(InvitacionRol(invitacion_id=inv.id, rol=r) for r in f.roles)
