"""Sesiones del panel en el servidor (I-6; ADR 0005, 0015, 0019, doc 06).

- La cookie lleva un identificador aleatorio de 256 bits; la DB guarda solo su HMAC con una
  llave derivada de SESSION_SECRET (32 bytes, como exige `sesion_hash_longitud`).
- El rol NO se guarda: se resuelve en cada petición con las listas vigentes de correos. Si el
  correo ya no está en ninguna lista (se quitó y se reinició la API), la sesión se borra.
- Vence tras 8 h sin actividad o a los 7 días (valores configurables).
- El estado de OAuth (state, nonce y verificador PKCE) viaja en una cookie temporal firmada.
"""

import base64
import enum
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.models import EventoAuditoria, SesionAdmin

COOKIE_SESION = "__Host-ma_sesion"
COOKIE_OAUTH = "__Host-ma_oauth"
OAUTH_VIGENCIA_S = 600
ACTIVIDAD_CADA = timedelta(minutes=5)  # no se escribe en la DB en cada petición
MIN_SECRETO_BYTES = 32


class Rol(enum.StrEnum):
    ADMIN = "admin"  # novios: acceso total
    LECTOR = "lector"  # planner: solo lectura + exportación


class SecretoInvalido(ValueError):
    pass


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


@dataclass(frozen=True)
class LlavesPanel:
    """Llaves derivadas de SESSION_SECRET, una por uso (separación de dominios)."""

    oauth: bytes
    sesion: bytes

    @classmethod
    def desde_secreto(cls, secreto: str) -> "LlavesPanel":
        try:
            crudo = _b64d(secreto.strip())
        except ValueError:
            raise SecretoInvalido("SESSION_SECRET no es base64url válido") from None
        if len(crudo) < MIN_SECRETO_BYTES:
            raise SecretoInvalido("SESSION_SECRET debe tener al menos 32 bytes")

        def derivar(uso: bytes) -> bytes:
            return hmac.new(crudo, b"ma-panel|v1|" + uso, hashlib.sha256).digest()

        return cls(oauth=derivar(b"oauth-state"), sesion=derivar(b"session-id"))


def generar_secreto_sesion() -> str:
    return _b64e(secrets.token_bytes(MIN_SECRETO_BYTES))


# --------------------------------------------------------------------------- estado de OAuth
@dataclass(frozen=True)
class EstadoOAuth:
    state: str
    nonce: str
    verificador: str
    emitido: int  # epoch s


def firmar_estado(llaves: LlavesPanel, estado: EstadoOAuth) -> str:
    carga = _b64e(
        json.dumps(
            {"s": estado.state, "n": estado.nonce, "v": estado.verificador, "t": estado.emitido},
            separators=(",", ":"),
        ).encode()
    )
    firma = _b64e(hmac.new(llaves.oauth, carga.encode("ascii"), hashlib.sha256).digest())
    return f"{carga}.{firma}"


def leer_estado(llaves: LlavesPanel, valor: str | None, ahora_epoch: int) -> EstadoOAuth | None:
    """None si falta, está alterada o venció (la vigencia también la limita Max-Age)."""
    if not valor or valor.count(".") != 1 or len(valor) > 1024:
        return None
    carga, firma = valor.split(".")
    esperada = _b64e(hmac.new(llaves.oauth, carga.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(firma, esperada):
        return None
    try:
        d = json.loads(_b64d(carga))
        estado = EstadoOAuth(str(d["s"]), str(d["n"]), str(d["v"]), int(d["t"]))
    except (ValueError, KeyError, TypeError):
        return None
    if not 0 <= ahora_epoch - estado.emitido <= OAUTH_VIGENCIA_S:
        return None
    return estado


# --------------------------------------------------------------------------- roles
@dataclass(frozen=True)
class Listas:
    novios: frozenset[str]
    planner: frozenset[str]

    def rol(self, correo: str) -> Rol | None:
        correo = correo.strip().lower()
        if correo in self.novios:
            return Rol.ADMIN
        if correo in self.planner:
            return Rol.LECTOR
        return None


# --------------------------------------------------------------------------- sesiones
@dataclass(frozen=True)
class Usuario:
    correo: str
    rol: Rol
    secreto_csrf: bytes

    @property
    def csrf_token(self) -> str:
        return _b64e(self.secreto_csrf)


@dataclass(frozen=True)
class Duraciones:
    inactividad: timedelta
    maxima: timedelta


def _hash(llaves: LlavesPanel, identificador: bytes) -> bytes:
    return hmac.new(llaves.sesion, identificador, hashlib.sha256).digest()


def _vencidas(ahora: datetime, d: Duraciones):  # noqa: ANN202
    return or_(
        SesionAdmin.expira_en <= ahora, SesionAdmin.ultima_actividad <= ahora - d.inactividad
    )


def crear_sesion(
    s: Session, llaves: LlavesPanel, correo: str, rol: Rol, ahora: datetime, d: Duraciones
) -> str:
    """Crea la sesión y devuelve el valor de la cookie (el identificador en claro)."""
    s.execute(delete(SesionAdmin).where(_vencidas(ahora, d)))  # limpieza de paso
    identificador = secrets.token_bytes(32)
    s.add(
        SesionAdmin(
            hash_sesion=_hash(llaves, identificador),
            correo=correo,
            secreto_csrf=secrets.token_bytes(32),
            creada_en=ahora,
            ultima_actividad=ahora,
            expira_en=ahora + d.maxima,
        )
    )
    s.add(EventoAuditoria(actor=correo, accion="login", detalle={"rol": rol.value}))
    return _b64e(identificador)


def _identificador(valor: str | None) -> bytes | None:
    if not valor or len(valor) > 64:
        return None
    try:
        crudo = _b64d(valor)
    except ValueError:
        return None
    return crudo if len(crudo) == 32 else None


def buscar_sesion(
    s: Session,
    llaves: LlavesPanel,
    listas: Listas,
    valor_cookie: str | None,
    ahora: datetime,
    d: Duraciones,
) -> Usuario | None:
    """Usuario de la sesión, o None (y la sesión se borra) si no existe, venció o el correo ya
    no está en ninguna lista."""
    identificador = _identificador(valor_cookie)
    if identificador is None:
        return None
    hash_sesion = _hash(llaves, identificador)
    fila = s.get(SesionAdmin, hash_sesion)
    if fila is None:
        return None
    rol = listas.rol(fila.correo)
    vencida = ahora >= fila.expira_en or ahora - fila.ultima_actividad >= d.inactividad
    if vencida or rol is None:
        s.execute(delete(SesionAdmin).where(SesionAdmin.hash_sesion == hash_sesion))
        return None
    if ahora - fila.ultima_actividad >= ACTIVIDAD_CADA:
        s.execute(
            update(SesionAdmin)
            .where(SesionAdmin.hash_sesion == hash_sesion)
            .values(ultima_actividad=ahora)
        )
    return Usuario(correo=fila.correo, rol=rol, secreto_csrf=fila.secreto_csrf)


def cerrar_sesion(s: Session, llaves: LlavesPanel, valor_cookie: str | None) -> str | None:
    """Borra la sesión en el servidor. Devuelve el correo si existía."""
    identificador = _identificador(valor_cookie)
    if identificador is None:
        return None
    hash_sesion = _hash(llaves, identificador)
    correo = s.scalar(select(SesionAdmin.correo).where(SesionAdmin.hash_sesion == hash_sesion))
    s.execute(delete(SesionAdmin).where(SesionAdmin.hash_sesion == hash_sesion))
    if correo is not None:
        s.add(EventoAuditoria(actor=correo, accion="logout", detalle={}))
    return correo


def csrf_valido(usuario: Usuario, encabezado: str | None) -> bool:
    if not encabezado or len(encabezado) > 128:
        return False
    return hmac.compare_digest(encabezado.encode("ascii", "replace"), usuario.csrf_token.encode())
