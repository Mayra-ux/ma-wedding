"""Enlaces de invitación: generar, regenerar, revocar, archivar, consultar, buscar y rotar llaves.

Capa de servicio (fase I-3). Las rutas HTTP se conectan en I-4 (consulta pública) e I-7
(panel); cada error trae su `codigo` y `status` (docs/architecture/07-contratos-api.md).

Reglas:
- Toda operación que cambia enlaces bloquea antes la invitación (SELECT … FOR UPDATE).
- No se genera enlace para invitaciones en revisión o archivadas (M8, ADR 0009/0017).
- Regenerar, revocar o archivar invalida el token anterior al instante (D5).
- El token en claro nunca se guarda ni se registra: solo se devuelve en memoria.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import guardas  # noqa: F401  (guarda contra DELETE de invitaciones)
from app.models import Enlace, Invitacion
from app.respuestas import bloquear_invitacion
from app.tokens import (
    OCULTO,
    Llaves,
    TokenEnClaro,
    armar_url,
    cifrar,
    descifrar,
    hmac_token,
    nuevo_token,
    parsear_token,
)


# --------------------------------------------------------------------------- errores
class ErrorEnlace(Exception):
    codigo = "error"
    status = 500

    def __init__(self) -> None:
        super().__init__(self.codigo)  # el mensaje es solo el código: nunca datos ni tokens


class EnlaceNoValido(ErrorEnlace):
    """Respuesta única para token mal formado, inexistente, revocado o de invitación archivada."""

    codigo, status = "enlace_no_valido", 404


class SinEnlaceActivo(ErrorEnlace):
    codigo, status = "sin_enlace_activo", 404


class RequiereRevision(ErrorEnlace):
    codigo, status = "requiere_revision", 409


class Archivada(ErrorEnlace):
    codigo, status = "archivada", 409


class YaTieneEnlace(ErrorEnlace):
    codigo, status = "ya_tiene_enlace", 409


class YaArchivada(ErrorEnlace):
    codigo, status = "ya_archivada", 409


# --------------------------------------------------------------------------- resultado
@dataclass(frozen=True, repr=False)
class EnlaceGenerado:
    token: TokenEnClaro
    origen: str

    @property
    def url(self) -> str:
        return armar_url(self.origen, self.token)

    def __repr__(self) -> str:
        return f"EnlaceGenerado({self.origen}/#t={OCULTO})"

    __str__ = __repr__


# --------------------------------------------------------------------------- internos
def _activo(session: Session, invitacion_id: int) -> Enlace | None:
    return session.scalar(
        select(Enlace)
        .where(Enlace.invitacion_id == invitacion_id, Enlace.revocado_en.is_(None))
        .with_for_update()
    )


def _validar_generable(inv: Invitacion) -> None:
    if inv.archivada_en is not None:
        raise Archivada()
    if inv.requiere_revision:
        raise RequiereRevision()


def _crear(session: Session, inv: Invitacion, llaves: Llaves) -> TokenEnClaro:
    token = nuevo_token()
    blob, kid = cifrar(llaves, token.raw, inv.id)
    session.add(
        Enlace(
            invitacion_id=inv.id,
            hmac_token=hmac_token(llaves.hash_actual, token.raw),
            token_cifrado=blob,
            id_llave=kid,
        )
    )
    session.flush()
    return token


def _revocar(session: Session, enlace: Enlace) -> None:
    enlace.revocado_en = func.now()
    session.flush()  # antes de insertar otro (índice único parcial enlace_uno_activo)


# --------------------------------------------------------------------------- operaciones
def generar_enlace(
    session: Session, invitacion_id: int, llaves: Llaves, origen: str
) -> EnlaceGenerado:
    inv = bloquear_invitacion(session, invitacion_id)
    _validar_generable(inv)
    if _activo(session, inv.id) is not None:
        raise YaTieneEnlace()
    return EnlaceGenerado(_crear(session, inv, llaves), origen)


def regenerar_enlace(
    session: Session, invitacion_id: int, llaves: Llaves, origen: str
) -> EnlaceGenerado:
    inv = bloquear_invitacion(session, invitacion_id)
    _validar_generable(inv)
    activo = _activo(session, inv.id)
    if activo is not None:
        _revocar(session, activo)
    token = _crear(session, inv, llaves)
    inv.enlace_enviado_en = None  # regenerar reinicia la marca de enviado (ADR 0017)
    inv.enlace_enviado_origen = None
    session.flush()
    return EnlaceGenerado(token, origen)


def revocar_enlace(session: Session, invitacion_id: int) -> None:
    inv = bloquear_invitacion(session, invitacion_id)
    activo = _activo(session, inv.id)
    if activo is None:
        raise SinEnlaceActivo()
    _revocar(session, activo)


def archivar_invitacion(session: Session, invitacion_id: int) -> None:
    """Archiva y revoca el enlace en la misma transacción (ADR 0017)."""
    inv = bloquear_invitacion(session, invitacion_id)
    if inv.archivada_en is not None:
        raise YaArchivada()
    inv.archivada_en = func.now()
    activo = _activo(session, inv.id)
    if activo is not None:
        _revocar(session, activo)
    session.flush()


def obtener_enlace(
    session: Session, invitacion_id: int, llaves: Llaves, origen: str
) -> EnlaceGenerado:
    """Descifra la copia del enlace activo para mostrarlo o reenviarlo (solo novios)."""
    activo = session.scalar(
        select(Enlace).where(Enlace.invitacion_id == invitacion_id, Enlace.revocado_en.is_(None))
    )
    if activo is None:
        raise SinEnlaceActivo()
    raw = descifrar(llaves, activo.token_cifrado, activo.invitacion_id, activo.id_llave)
    return EnlaceGenerado(TokenEnClaro(raw), origen)


def buscar_por_token(session: Session, texto: object, llaves: Llaves) -> Invitacion:
    """Invitación de un token válido y activo. Cualquier fallo → EnlaceNoValido (idéntico)."""
    raw = parsear_token(texto)
    if raw is None:
        raise EnlaceNoValido()
    for llave in llaves.hashes:  # actual y, durante una rotación, la anterior
        inv = session.scalar(
            select(Invitacion)
            .join(Enlace, Enlace.invitacion_id == Invitacion.id)
            .where(
                Enlace.hmac_token == hmac_token(llave, raw),
                Enlace.revocado_en.is_(None),
                Invitacion.archivada_en.is_(None),
            )
        )
        if inv is not None:
            return inv
    raise EnlaceNoValido()


# --------------------------------------------------------------------------- rotación
@dataclass(frozen=True)
class InformeRotacion:
    enlaces: int
    recifrados: int
    al_dia: int


def rotar_llaves(session: Session, llaves: Llaves) -> InformeRotacion:
    """Vuelve a cifrar cada copia con la llave actual y recalcula su HMAC (ADR 0019).

    Recorre todos los enlaces, incluidos los revocados, para poder retirar la llave anterior.
    Es idempotente. Si una copia no se puede descifrar, lanza CopiaIlegible y la transacción
    del llamador se revierte completa (nada queda a medias).
    """
    enlaces = session.scalars(select(Enlace).order_by(Enlace.id).with_for_update()).all()
    recifrados = 0
    for e in enlaces:
        raw = descifrar(llaves, e.token_cifrado, e.invitacion_id, e.id_llave)
        nuevo_hmac = hmac_token(llaves.hash_actual, raw)
        if e.id_llave == llaves.id_actual and e.hmac_token == nuevo_hmac:
            continue
        e.token_cifrado, e.id_llave = cifrar(llaves, raw, e.invitacion_id)
        e.hmac_token = nuevo_hmac
        recifrados += 1
    session.flush()
    return InformeRotacion(len(enlaces), recifrados, len(enlaces) - recifrados)
