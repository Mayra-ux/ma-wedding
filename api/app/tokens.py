"""Tokens de invitación: generación, HMAC de búsqueda y copia cifrada (ADR 0008, 0013, 0019).

- Token: 128 bits aleatorios, base64url sin relleno → 22 caracteres, forma canónica.
- Búsqueda: HMAC-SHA-256(TOKEN_HASH_KEY, 16 bytes del token) → 32 bytes.
- Copia: AES-256-GCM, nonce aleatorio de 96 bits; se guarda nonce ‖ cifrado ‖ etiqueta (44 bytes)
  con el identificador de la llave. El AAD ata la copia a su invitación y a su llave.

El token en claro solo vive en memoria dentro de `TokenEnClaro`, cuyo repr/str lo ocultan.
Nunca se guarda en la DB ni se registra en logs.
"""

import base64
import binascii
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TOKEN_BYTES = 16
TOKEN_LEN = 22
KEY_BYTES = 32
NONCE_BYTES = 12
CIFRADO_LEN = NONCE_BYTES + TOKEN_BYTES + 16  # 44: nonce + cifrado + etiqueta GCM
OCULTO = "<token oculto>"

_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{22}")
_KEY_ID_RE = re.compile(r"[a-z0-9_-]{1,32}")  # mismo formato que exige la DB (enlace.id_llave)


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


# --------------------------------------------------------------------------- token
class TokenEnClaro:
    """Token en memoria. `repr`, `str` y `format` lo ocultan; solo `.valor` lo expone."""

    __slots__ = ("_raw",)

    def __init__(self, raw: bytes) -> None:
        if len(raw) != TOKEN_BYTES:
            raise ValueError("el token debe tener 16 bytes")
        self._raw = raw

    @property
    def valor(self) -> str:
        return _b64e(self._raw)

    @property
    def raw(self) -> bytes:
        return self._raw

    def __repr__(self) -> str:
        return OCULTO

    __str__ = __repr__

    def __format__(self, spec: str) -> str:
        return OCULTO

    def __reduce__(self) -> object:  # evita que se serialice por accidente
        raise TypeError("TokenEnClaro no se puede serializar")


def nuevo_token() -> TokenEnClaro:
    return TokenEnClaro(secrets.token_bytes(TOKEN_BYTES))


def parsear_token(texto: object) -> bytes | None:
    """Devuelve los 16 bytes si `texto` es un token en forma canónica; si no, None."""
    if not isinstance(texto, str) or not _TOKEN_RE.fullmatch(texto):
        return None
    try:
        raw = _b64d(texto)
    except (binascii.Error, ValueError):
        return None
    # 22 caracteres llevan 132 bits: los 4 sobrantes deben ser cero (una sola escritura válida).
    if len(raw) != TOKEN_BYTES or _b64e(raw) != texto:
        return None
    return raw


def armar_url(origen: str, token: TokenEnClaro) -> str:
    """Enlace de la invitación: https://<dominio>/#t=<token> (ADR 0013)."""
    return f"{origen}/#t={token.valor}"


# --------------------------------------------------------------------------- llaves
class LlavesNoConfiguradas(RuntimeError):
    """Faltan TOKEN_HASH_KEY o TOKEN_ENCRYPTION_KEYS."""


class LlavesInvalidas(ValueError):
    """Formato inválido. El mensaje nunca incluye el valor de la llave."""


@dataclass(frozen=True)
class Llaves:
    hash_actual: bytes = field(repr=False)
    hash_anterior: bytes | None = field(repr=False)
    cifrado: dict[str, bytes] = field(repr=False)  # id → llave; el primero es el actual
    id_actual: str

    @property
    def hashes(self) -> tuple[bytes, ...]:
        return (self.hash_actual,) + ((self.hash_anterior,) if self.hash_anterior else ())


def _llave_32(texto: str, nombre: str) -> bytes:
    try:
        raw = _b64d(texto.strip())
    except (binascii.Error, ValueError):
        raise LlavesInvalidas(f"{nombre}: no es base64url válido") from None
    if len(raw) != KEY_BYTES:
        raise LlavesInvalidas(f"{nombre}: debe decodificar a {KEY_BYTES} bytes")
    return raw


def parsear_llaves(
    hash_key: str | None, hash_key_previous: str | None, encryption_keys: str | None
) -> Llaves:
    if not hash_key or not encryption_keys:
        raise LlavesNoConfiguradas("Faltan TOKEN_HASH_KEY o TOKEN_ENCRYPTION_KEYS.")
    cifrado: dict[str, bytes] = {}
    for i, parte in enumerate(encryption_keys.split(",")):
        kid, sep, valor = parte.strip().partition(":")
        if not sep or not _KEY_ID_RE.fullmatch(kid):
            raise LlavesInvalidas(
                f"TOKEN_ENCRYPTION_KEYS[{i}]: se espera id:llave con id ^[a-z0-9_-]{{1,32}}$"
            )
        if kid in cifrado:
            raise LlavesInvalidas(f"TOKEN_ENCRYPTION_KEYS: id repetido '{kid}'")
        cifrado[kid] = _llave_32(valor, f"TOKEN_ENCRYPTION_KEYS[{kid}]")
    anterior = (
        _llave_32(hash_key_previous, "TOKEN_HASH_KEY_PREVIOUS") if hash_key_previous else None
    )
    return Llaves(
        hash_actual=_llave_32(hash_key, "TOKEN_HASH_KEY"),
        hash_anterior=anterior,
        cifrado=cifrado,
        id_actual=next(iter(cifrado)),
    )


def generar_llaves_env(hoy: datetime | None = None) -> dict[str, str]:
    """Llaves nuevas (aleatorias) en el formato de las variables de entorno."""
    kid = "k" + (hoy or datetime.now(UTC)).strftime("%Y%m%d")
    return {
        "TOKEN_HASH_KEY": _b64e(secrets.token_bytes(KEY_BYTES)),
        "TOKEN_ENCRYPTION_KEYS": f"{kid}:{_b64e(secrets.token_bytes(KEY_BYTES))}",
    }


# --------------------------------------------------------------------------- HMAC y cifrado
def hmac_token(llave: bytes, raw: bytes) -> bytes:
    return hmac.new(llave, raw, hashlib.sha256).digest()


def _aad(invitacion_id: int, id_llave: str) -> bytes:
    return f"enlace|v1|{invitacion_id}|{id_llave}".encode()


def cifrar(llaves: Llaves, raw: bytes, invitacion_id: int) -> tuple[bytes, str]:
    kid = llaves.id_actual
    nonce = secrets.token_bytes(NONCE_BYTES)
    cifrado = AESGCM(llaves.cifrado[kid]).encrypt(nonce, raw, _aad(invitacion_id, kid))
    return nonce + cifrado, kid


class CopiaIlegible(RuntimeError):
    """No se pudo descifrar la copia (llave ausente, copia alterada o movida de fila)."""


def descifrar(llaves: Llaves, blob: bytes, invitacion_id: int, id_llave: str) -> bytes:
    llave = llaves.cifrado.get(id_llave)
    if llave is None:
        raise CopiaIlegible(f"llave '{id_llave}' no configurada")
    if len(blob) != CIFRADO_LEN:
        raise CopiaIlegible("longitud de la copia inválida")
    try:
        raw = AESGCM(llave).decrypt(
            blob[:NONCE_BYTES], blob[NONCE_BYTES:], _aad(invitacion_id, id_llave)
        )
    except InvalidTag:
        raise CopiaIlegible("la copia no corresponde a esta invitación o llave") from None
    if len(raw) != TOKEN_BYTES:
        raise CopiaIlegible("contenido inesperado")
    return raw
