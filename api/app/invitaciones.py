"""Servicio de la API del panel (I-7; ADR 0006, 0007, 0016, 0017, 0026, 0027; doc 02 y 05).

- Toda escritura sobre una invitación existente bloquea su fila con SELECT … FOR UPDATE.
- Los novios no tienen congelamiento (ADR 0027): solo el desbloqueo depende del congelamiento
  de los invitados, porque es para ellos.
- La auditoría nunca guarda datos de los invitados: solo nombres de campos, números, catálogos
  y fechas del sistema (M14).
- Los errores llevan un código estable del contrato 07 y nunca valores recibidos.
"""

import re
import urllib.parse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import BigInteger, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import guardas  # noqa: F401  (guarda contra DELETE de invitaciones)
from app.catalogos import GRUPOS, LADOS, MOTIVOS_REVISION, ROLES_BODA
from app.errores import ErrorAPI
from app.esquemas import MAX_ALERGIAS, MAX_MENSAJE, normalizar_texto
from app.esquemas_panel import EntradaEdicion, EntradaInvitacion, EntradaRespuestaAdmin
from app.estado import fecha_limite_mostrar, iso_mx
from app.models import (
    ConfiguracionEvento,
    Enlace,
    EventoAuditoria,
    Invitacion,
    InvitacionRol,
    RecordatorioEnviado,
    VersionRespuesta,
)
from app.respuestas import registrar_respuesta

MAX_NOMBRE = 120
MAX_NOTA = 500
MAX_CONTACTO = 120


# --------------------------------------------------------------------------- utilidades
def auditar(
    s: Session, actor: str, accion: str, codigo: str | None = None, detalle: dict | None = None
) -> None:
    s.add(
        EventoAuditoria(actor=actor, accion=accion, codigo_invitacion=codigo, detalle=detalle or {})
    )


def configuracion(s: Session) -> ConfiguracionEvento:
    return s.get(ConfiguracionEvento, 1, populate_existing=True)


def buscar(s: Session, codigo: str, *, bloquear: bool = False) -> Invitacion:
    consulta = select(Invitacion).where(Invitacion.codigo == codigo)
    if bloquear:
        consulta = consulta.with_for_update()
    inv = s.scalar(consulta.execution_options(populate_existing=True))
    if inv is None:
        raise ErrorAPI(404, "no_encontrado")
    return inv


def no_archivada(inv: Invitacion) -> None:
    if inv.archivada_en is not None:
        raise ErrorAPI(409, "archivada")


def _vigente(s: Session, invitacion_id: int) -> VersionRespuesta | None:
    return s.scalar(
        select(VersionRespuesta).where(
            VersionRespuesta.invitacion_id == invitacion_id, VersionRespuesta.vigente
        )
    )


# --------------------------------------------------------------------------- validaciones
_SEPARADORES = re.compile(r"[\s\-().]")
_E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")


def normalizar_telefono(valor: str | None, campo: str) -> str | None:
    """10 dígitos → +52 (México). Con lada internacional (+…) → E.164. Otro → 422 (M11)."""
    if valor is None:
        return None
    limpio = _SEPARADORES.sub("", valor)
    if not limpio:
        return None
    if re.fullmatch(r"[0-9]{10}", limpio):
        return "+52" + limpio
    if limpio.startswith("00"):  # 0052… → +52…
        limpio = "+" + limpio[2:]
    if _E164.fullmatch(limpio):
        return limpio
    raise ErrorAPI(422, "validacion", {campo: "telefono_invalido"})


def _texto(valor: str | None, campo: str, maximo: int) -> str | None:
    return normalizar_texto(valor, campo, maximo)


def _entero(valor: int | None, campo: str, minimo: int, maximo: int = 10_000) -> int | None:
    if valor is not None and not minimo <= valor <= maximo:
        raise ErrorAPI(422, "validacion", {campo: "fuera_de_rango"})
    return valor


def _catalogo(valor: str | None, campo: str, opciones: tuple[str, ...]) -> str | None:
    if valor is not None and valor not in opciones:
        raise ErrorAPI(422, "validacion", {campo: "fuera_de_catalogo"})
    return valor


def _roles(roles: list[str]) -> list[str]:
    if any(r not in ROLES_BODA for r in roles):
        raise ErrorAPI(422, "validacion", {"roles": "fuera_de_catalogo"})
    if len(set(roles)) != len(roles):
        raise ErrorAPI(422, "validacion", {"roles": "repetido"})
    return sorted(roles, key=ROLES_BODA.index)


# Validadores por campo editable: (nombre → función que normaliza y valida).
_VALIDAR = {
    "nombre_mostrar": lambda v: _texto(v, "nombre_mostrar", MAX_NOMBRE),
    "adultos": lambda v: _entero(v, "adultos", 1),
    "ninos_autorizados": lambda v: _entero(v, "ninos_autorizados", 0),
    "infantes": lambda v: _entero(v, "infantes", 0),
    "lado": lambda v: _catalogo(v, "lado", LADOS),
    "grupo": lambda v: _catalogo(v, "grupo", GRUPOS),
    "mesa": lambda v: _entero(v, "mesa", 1),
    "nota_interna": lambda v: _texto(v, "nota_interna", MAX_NOTA),
    "no_planner": lambda v: _entero(v, "no_planner", 1, 1_000_000),
    "telefono_principal": lambda v: normalizar_telefono(v, "telefono_principal"),
    "contacto_alterno_nombre": lambda v: _texto(v, "contacto_alterno_nombre", MAX_CONTACTO),
    "contacto_alterno_tel": lambda v: normalizar_telefono(v, "contacto_alterno_tel"),
}
_OBLIGATORIOS = {"nombre_mostrar", "adultos", "ninos_autorizados", "infantes"}


def _validar_campos(datos: dict) -> dict:
    """Valida y normaliza. Reúne todos los errores de campo en un solo 422."""
    limpios, errores = {}, {}
    for campo, valor in datos.items():
        try:
            limpios[campo] = _roles(valor) if campo == "roles" else _VALIDAR[campo](valor)
        except ErrorAPI as exc:
            errores.update(exc.fields or {})
    for campo in _OBLIGATORIOS & set(datos):
        if limpios.get(campo) is None and campo not in errores:
            errores[campo] = "obligatorio"
    if errores:
        raise ErrorAPI(422, "validacion", errores)
    return limpios


def _recalcular_revision(inv: Invitacion, cambiados: set[str]) -> None:
    """E8: `pases_inconsistentes` solo si el "# Pases" original no cuadra con adultos + niños.
    Los motivos de catálogo o teléfono se quitan al guardar un valor válido en ese campo."""
    motivos = set(inv.motivos_revision or [])
    pases = inv.adultos + inv.ninos_autorizados
    if inv.pases_planner_original is not None and inv.pases_planner_original != pases:
        motivos.add("pases_inconsistentes")
    else:
        motivos.discard("pases_inconsistentes")
    for campo, motivo in (
        ("lado", "lado_invalido"),
        ("grupo", "grupo_invalido"),
        ("roles", "rol_invalido"),
    ):
        if campo in cambiados:
            motivos.discard(motivo)
    if {"telefono_principal", "contacto_alterno_tel"} & cambiados:
        motivos.discard("telefono_invalido")
    inv.motivos_revision = sorted(motivos, key=MOTIVOS_REVISION.index)
    inv.requiere_revision = bool(motivos)


# --------------------------------------------------------------------------- alta y edición
def _siguiente_codigo(s: Session) -> str:
    n = s.scalar(
        select(func.coalesce(func.max(func.substr(Invitacion.codigo, 5).cast(BigInteger)), 0))
    )
    return f"INV-{n + 1:03d}"


def crear(s: Session, entrada: EntradaInvitacion, actor: str) -> Invitacion:
    datos = _validar_campos(entrada.model_dump())
    roles = datos.pop("roles")
    for _intento in range(5):
        codigo = _siguiente_codigo(s)
        try:
            with s.begin_nested():
                inv = Invitacion(codigo=codigo, **datos)
                s.add(inv)
                s.flush()
        except IntegrityError:
            continue  # otra alta tomó el mismo código: se reintenta con el siguiente
        s.add_all(InvitacionRol(invitacion_id=inv.id, rol=r) for r in roles)
        auditar(s, actor, "invitacion_creada", codigo)
        s.flush()
        return inv
    raise ErrorAPI(409, "conflicto_codigo")


def editar(s: Session, codigo: str, entrada: EntradaEdicion, actor: str) -> Invitacion:
    enviados = {c: getattr(entrada, c) for c in entrada.model_fields_set}
    datos = _validar_campos(enviados)
    inv = buscar(s, codigo, bloquear=True)
    no_archivada(inv)
    roles_actuales = _roles_de(s, inv.id)
    cambiados = set()
    for campo, valor in datos.items():
        if campo == "roles":
            if valor != roles_actuales:
                cambiados.add("roles")
        elif getattr(inv, campo) != valor:
            cambiados.add(campo)
    adultos = datos.get("adultos", inv.adultos)
    ninos = datos.get("ninos_autorizados", inv.ninos_autorizados)
    vigente = _vigente(s, inv.id)
    if vigente is not None and vigente.confirmados > adultos + ninos:
        raise ErrorAPI(409, "pases_menores_que_confirmados")
    for campo in cambiados - {"roles"}:
        setattr(inv, campo, datos[campo])
    if "roles" in cambiados:
        s.execute(delete(InvitacionRol).where(InvitacionRol.invitacion_id == inv.id))
        s.add_all(InvitacionRol(invitacion_id=inv.id, rol=r) for r in datos["roles"])
    _recalcular_revision(inv, set(datos))
    if cambiados:
        auditar(s, actor, "invitacion_editada", codigo, {"campos": sorted(cambiados)})
    try:
        with s.begin_nested():
            s.flush()
    except IntegrityError as exc:
        # Segunda defensa: el disparador M6 de la DB (si la comprobación de arriba fallara).
        if _restriccion(exc) == "invitacion_pases_no_bajo_confirmados":
            raise ErrorAPI(409, "pases_menores_que_confirmados") from None
        raise
    return inv


def _restriccion(exc: IntegrityError) -> str | None:
    diag = getattr(getattr(exc, "orig", None), "diag", None)
    return getattr(diag, "constraint_name", None)


def archivar(s: Session, codigo: str, actor: str) -> None:
    from app.enlaces import YaArchivada, archivar_invitacion

    inv = buscar(s, codigo, bloquear=True)
    try:
        archivar_invitacion(s, inv.id)
    except YaArchivada:
        raise ErrorAPI(409, "ya_archivada") from None
    auditar(s, actor, "invitacion_archivada", codigo)


def restaurar(s: Session, codigo: str, actor: str) -> None:
    inv = buscar(s, codigo, bloquear=True)
    if inv.archivada_en is None:
        raise ErrorAPI(409, "no_archivada")
    inv.archivada_en = None
    auditar(s, actor, "invitacion_restaurada", codigo)
    s.flush()


# --------------------------------------------------------------------------- desbloqueo
def desbloquear(s: Session, codigo: str, hasta: datetime, ahora: datetime, actor: str) -> None:
    """M13: solo después del plazo, hasta el congelamiento de los invitados como máximo."""
    inv = buscar(s, codigo, bloquear=True)
    no_archivada(inv)
    config = configuracion(s)
    if ahora >= config.congelamiento:
        raise ErrorAPI(409, "rsvp_congelado")
    if ahora < config.cierre_plazo:
        raise ErrorAPI(409, "plazo_aun_abierto")
    if hasta <= ahora:
        raise ErrorAPI(422, "validacion", {"hasta": "en_el_pasado"})
    if hasta > config.congelamiento:
        raise ErrorAPI(422, "mas_alla_del_congelamiento")
    inv.desbloqueada_hasta = hasta
    auditar(s, actor, "desbloqueo", codigo, {"hasta": iso_mx(hasta)})
    s.flush()


def retirar_desbloqueo(s: Session, codigo: str, actor: str) -> None:
    inv = buscar(s, codigo, bloquear=True)
    if inv.desbloqueada_hasta is not None:
        inv.desbloqueada_hasta = None
        auditar(s, actor, "desbloqueo_retirado", codigo)
        s.flush()


# --------------------------------------------------------------------------- respuesta del admin
def responder_como_admin(
    s: Session, codigo: str, entrada: EntradaRespuestaAdmin, actor: str
) -> VersionRespuesta:
    """Los novios registran respuestas en cualquier momento, sin congelamiento (ADR 0027)."""
    errores = {}
    textos = {}
    for campo, valor, maximo in (
        ("alergias", entrada.alergias, MAX_ALERGIAS),
        ("mensaje", entrada.mensaje, MAX_MENSAJE),
    ):
        try:
            textos[campo] = normalizar_texto(valor, campo, maximo)
        except ErrorAPI as exc:
            errores.update(exc.fields or {})
    if errores:
        raise ErrorAPI(422, "validacion", errores)
    inv = buscar(s, codigo, bloquear=True)
    no_archivada(inv)
    if entrada.asiste:
        if not 1 <= entrada.confirmados <= inv.pases:
            raise ErrorAPI(422, "confirmados_fuera_de_rango")
    elif entrada.confirmados != 0:
        raise ErrorAPI(422, "confirmados_fuera_de_rango")
    version = registrar_respuesta(
        s,
        inv.id,
        asiste=entrada.asiste,
        confirmados=entrada.confirmados,
        alergias=textos["alergias"] if entrada.asiste else None,  # B5
        mensaje=textos["mensaje"],
        origen="admin",
        actor=actor,
    )
    auditar(
        s,
        actor,
        "respuesta_admin",
        codigo,
        {"asiste": entrada.asiste, "confirmados": entrada.confirmados},
    )
    s.refresh(version)
    return version


# --------------------------------------------------------------------------- envío del enlace
def marcar_enlace_enviado(
    s: Session, codigo: str, origen: str, ahora: datetime, actor: str
) -> None:
    inv = buscar(s, codigo, bloquear=True)
    activo = s.scalar(
        select(Enlace.id).where(Enlace.invitacion_id == inv.id, Enlace.revocado_en.is_(None))
    )
    if activo is None:
        raise ErrorAPI(404, "sin_enlace_activo")
    inv.enlace_enviado_en = ahora
    inv.enlace_enviado_origen = origen
    auditar(s, actor, "enlace_marcado_enviado", codigo, {"origen": origen})
    s.flush()


# --------------------------------------------------------------------------- lectura
def _roles_de(s: Session, invitacion_id: int) -> list[str]:
    roles = s.scalars(
        select(InvitacionRol.rol).where(InvitacionRol.invitacion_id == invitacion_id)
    ).all()
    return sorted(roles, key=ROLES_BODA.index)


def _numero(codigo: str) -> int:
    return int(codigo[4:])


def _estado_respuesta(v: VersionRespuesta | None) -> str:
    if v is None:
        return "pendiente"
    return "confirmada" if v.asiste else "no_asiste"


def _fila(
    inv: Invitacion,
    v: VersionRespuesta | None,
    roles: list[str],
    enlace_activo: bool,
    recordatorios: list[RecordatorioEnviado],
) -> dict:
    """Una fila de la lista. Lleva indicadores del enlace, NUNCA su URL ni su token (ADR 0026)."""
    ultimo = recordatorios[-1] if recordatorios else None
    return {
        "codigo": inv.codigo,
        "nombre_mostrar": inv.nombre_mostrar,
        "adultos": inv.adultos,
        "ninos_autorizados": inv.ninos_autorizados,
        "infantes": inv.infantes,
        "pases": inv.adultos + inv.ninos_autorizados,
        "estado_respuesta": _estado_respuesta(v),
        "confirmados": v.confirmados if v is not None else None,
        "alergias": v.alergias if v is not None else None,
        "mensaje": v.mensaje if v is not None else None,
        "ultima_respuesta_en": iso_mx(v.creada_en) if v is not None else None,
        "ultima_respuesta_origen": v.origen if v is not None else None,
        "lado": inv.lado,
        "grupo": inv.grupo,
        "roles": roles,
        "mesa": inv.mesa,
        "nota_interna": inv.nota_interna,
        "no_planner": inv.no_planner,
        "telefono_principal": inv.telefono_principal,
        "contacto_alterno_nombre": inv.contacto_alterno_nombre,
        "contacto_alterno_tel": inv.contacto_alterno_tel,
        "requiere_revision": inv.requiere_revision,
        "motivos_revision": list(inv.motivos_revision or []),
        "desbloqueada_hasta": iso_mx(inv.desbloqueada_hasta),
        "enlace_activo": enlace_activo,
        "enlace_enviado": inv.enlace_enviado_en is not None,
        "enlace_enviado_en": iso_mx(inv.enlace_enviado_en),
        "enlace_enviado_origen": inv.enlace_enviado_origen,
        "recordatorios": len(recordatorios),
        "ultimo_recordatorio_en": iso_mx(ultimo.enviado_en) if ultimo else None,
        "ultimo_recordatorio_tipo": ultimo.tipo if ultimo else None,
        "archivada": inv.archivada_en is not None,
        "archivada_en": iso_mx(inv.archivada_en),
    }


def lista(s: Session, incluir_archivadas: bool) -> list[dict]:
    consulta = select(Invitacion)
    if not incluir_archivadas:
        consulta = consulta.where(Invitacion.archivada_en.is_(None))
    invs = sorted(s.scalars(consulta).all(), key=lambda i: _numero(i.codigo))
    vigentes = {
        v.invitacion_id: v
        for v in s.scalars(select(VersionRespuesta).where(VersionRespuesta.vigente))
    }
    activos = set(s.scalars(select(Enlace.invitacion_id).where(Enlace.revocado_en.is_(None))))
    roles: dict[int, list[str]] = defaultdict(list)
    for r in s.scalars(select(InvitacionRol)):
        roles[r.invitacion_id].append(r.rol)
    recs: dict[int, list[RecordatorioEnviado]] = defaultdict(list)
    for r in s.scalars(
        select(RecordatorioEnviado).order_by(RecordatorioEnviado.enviado_en, RecordatorioEnviado.id)
    ):
        recs[r.invitacion_id].append(r)
    return [
        _fila(
            i,
            vigentes.get(i.id),
            sorted(roles[i.id], key=ROLES_BODA.index),
            i.id in activos,
            recs[i.id],
        )
        for i in invs
    ]


def detalle(s: Session, codigo: str) -> dict:
    inv = buscar(s, codigo)
    activo = (
        s.scalar(
            select(Enlace.id).where(Enlace.invitacion_id == inv.id, Enlace.revocado_en.is_(None))
        )
        is not None
    )
    recs = s.scalars(
        select(RecordatorioEnviado)
        .where(RecordatorioEnviado.invitacion_id == inv.id)
        .order_by(RecordatorioEnviado.enviado_en, RecordatorioEnviado.id)
    ).all()
    fila = _fila(inv, _vigente(s, inv.id), _roles_de(s, inv.id), activo, list(recs))
    fila["pases_planner_original"] = inv.pases_planner_original
    fila["creada_en"] = iso_mx(inv.creada_en)
    fila["actualizada_en"] = iso_mx(inv.actualizada_en)
    return fila


def historial(s: Session, codigo: str) -> list[dict]:
    inv = buscar(s, codigo)
    versiones = s.scalars(
        select(VersionRespuesta)
        .where(VersionRespuesta.invitacion_id == inv.id)
        .order_by(VersionRespuesta.numero.desc())
    ).all()
    return [
        {
            "numero": v.numero,
            "vigente": v.vigente,
            "asiste": v.asiste,
            "confirmados": v.confirmados,
            "alergias": v.alergias,
            "mensaje": v.mensaje,
            "origen": v.origen,
            "actor": v.actor,
            "creada_en": iso_mx(v.creada_en),
        }
        for v in versiones
    ]


def auditoria(s: Session) -> list[dict]:
    eventos = s.scalars(select(EventoAuditoria).order_by(EventoAuditoria.id.desc())).all()
    return [
        {
            "actor": e.actor,
            "accion": e.accion,
            "codigo_invitacion": e.codigo_invitacion,
            "detalle": e.detalle,
            "creado_en": iso_mx(e.creado_en),
        }
        for e in eventos
    ]


def config_publica(s: Session) -> dict:
    c = configuracion(s)
    return {
        "cierre_plazo": iso_mx(c.cierre_plazo),
        "fecha_limite_mostrar": fecha_limite_mostrar(c.cierre_plazo).isoformat(),
        "congelamiento": iso_mx(c.congelamiento),
        "cierre_planner": iso_mx(c.cierre_planner),
        "fecha_borrado_1": c.fecha_borrado_1.isoformat(),
        "fecha_borrado_2": c.fecha_borrado_2.isoformat(),
    }


# --------------------------------------------------------------------------- resumen
def _vacio() -> dict:
    return {"invitaciones": 0, "pases": 0, "confirmados": 0}


def resumen(filas: list[dict]) -> dict:
    """Totales de las invitaciones activas (las archivadas no cuentan, A12)."""
    activas = [f for f in filas if not f["archivada"]]
    por_estado = {k: _vacio() for k in ("confirmada", "no_asiste", "pendiente")}
    por_lado = {k: _vacio() for k in (*LADOS, "sin_lado")}
    por_grupo = {k: _vacio() for k in (*GRUPOS, "sin_grupo")}
    por_rol = {k: _vacio() for k in ROLES_BODA}
    for f in activas:
        confirmados = f["confirmados"] or 0
        cubos = [
            por_estado[f["estado_respuesta"]],
            por_lado[f["lado"] or "sin_lado"],
            por_grupo[f["grupo"] or "sin_grupo"],
            *(por_rol[r] for r in f["roles"]),  # una invitación cuenta en cada rol (ADR 0017)
        ]
        for c in cubos:
            c["invitaciones"] += 1
            c["pases"] += f["pases"]
            c["confirmados"] += confirmados
    return {
        "invitaciones": len(activas),
        "pases_asignados": sum(f["pases"] for f in activas),
        "personas_confirmadas": sum(f["confirmados"] or 0 for f in activas),
        "ninos_autorizados": sum(f["ninos_autorizados"] for f in activas),
        "infantes": sum(f["infantes"] for f in activas),
        "por_estado": por_estado,
        "por_lado": por_lado,
        "por_grupo": por_grupo,
        "por_rol": por_rol,
    }


# --------------------------------------------------------------------------- recordatorios
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)  # fmt: skip

# Textos aprobados por los novios en I-9 (ADR 0026, 0029). Los recordatorios nunca llevan
# el enlace; solo el mensaje de envío del enlace (solo novios) lo incluye.
TEXTO_ENLACE = (
    "Hola, {nombre}: con mucha ilusión te invitamos a nuestra boda el sábado 6 de marzo de "
    "2027. Es peligroso ir solo… ¡acompáñanos! Aquí está tu invitación, donde puedes confirmar "
    "tu asistencia a más tardar el {fecha}:\n{enlace}\nCon cariño, Mayra y Alejandro"
)
TEXTO_CONFIRMAR = (
    "Hola, te recordamos confirmar tu asistencia a la boda de Mayra y Alejandro a más tardar "
    "el {fecha}, desde el enlace que te enviamos por WhatsApp. Si no lo encuentras, escríbenos "
    "y te lo reenviamos."
)
TEXTO_EVENTO = (
    "Hola, te recordamos que la boda de Mayra y Alejandro es el sábado 6 de marzo de 2027: "
    "ceremonia a la 1:00 p. m. en el Templo San Francisco de Asís y recepción a las 4:00 p. m. "
    "en La Viña Jardín de Eventos. ¡Te esperamos!"
)


def fecha_larga(d) -> str:  # noqa: ANN001
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]} de {d.year}"


@dataclass(frozen=True)
class Recordatorio:
    tipo: str
    texto: str
    telefono: str

    @property
    def wa_url(self) -> str:
        return f"https://wa.me/{self.telefono.lstrip('+')}?text={urllib.parse.quote(self.texto)}"


def tipo_de_recordatorio(config: ConfiguracionEvento, ahora: datetime) -> str:
    """Hasta el 30 ene: confirmar. Del 31 ene al 6 mar: evento. Después: cerrado (ADR 0026/27)."""
    if ahora < config.cierre_plazo:
        return "confirmar"
    if ahora < config.cierre_planner:
        return "evento"
    raise ErrorAPI(409, "recordatorios_cerrados")


def recordatorio(s: Session, codigo: str, destino: str, ahora: datetime) -> Recordatorio:
    inv = buscar(s, codigo)
    no_archivada(inv)
    config = configuracion(s)
    tipo = tipo_de_recordatorio(config, ahora)
    telefono = inv.telefono_principal if destino == "principal" else inv.contacto_alterno_tel
    if not telefono:
        raise ErrorAPI(409, "sin_telefono")
    texto = (
        TEXTO_CONFIRMAR.format(fecha=fecha_larga(fecha_limite_mostrar(config.cierre_plazo)))
        if tipo == "confirmar"
        else TEXTO_EVENTO
    )
    return Recordatorio(tipo=tipo, texto=texto, telefono=telefono)


def mensaje_enlace(s: Session, inv: Invitacion, destino: str, url: str) -> Recordatorio:
    """Mensaje de WhatsApp con el enlace personal (solo novios; ADR 0029)."""
    no_archivada(inv)
    telefono = inv.telefono_principal if destino == "principal" else inv.contacto_alterno_tel
    if not telefono:
        raise ErrorAPI(409, "sin_telefono")
    fecha = fecha_larga(fecha_limite_mostrar(configuracion(s).cierre_plazo))
    texto = TEXTO_ENLACE.format(nombre=inv.nombre_mostrar, fecha=fecha, enlace=url)
    return Recordatorio(tipo="enlace", texto=texto, telefono=telefono)


def marcar_recordatorio(s: Session, codigo: str, destino: str, ahora: datetime, actor: str) -> str:
    rec = recordatorio(s, codigo, destino, ahora)  # valida fase, archivada y teléfono
    inv = buscar(s, codigo, bloquear=True)
    s.add(
        RecordatorioEnviado(
            invitacion_id=inv.id, tipo=rec.tipo, destino=destino, actor=actor, enviado_en=ahora
        )
    )
    auditar(s, actor, "recordatorio_enviado", codigo, {"tipo": rec.tipo, "destino": destino})
    s.flush()
    return rec.tipo
