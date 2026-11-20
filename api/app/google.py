"""Inicio de sesión con Google: OIDC code flow con PKCE en el servidor (ADR 0005, doc 06).

- El canje del código lo hace la API; el panel nunca maneja tokens de Google.
- El id_token se verifica con PyJWT: firma RS256 con las llaves públicas de Google (en caché),
  emisor, audiencia, vigencia, nonce y `email_verified`.
- Las peticiones a Google usan urllib (biblioteca estándar) con timeout. Las pruebas
  reemplazan `ProveedorGoogle` por un simulado: nunca usan la red.
- Ningún error ni log incluye el código, el id_token ni el correo (ADR 0019).
"""

import base64
import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

import jwt

AUTORIZACION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 (es una URL pública)
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
EMISORES = ("https://accounts.google.com", "accounts.google.com")
ALCANCE = "openid email"
TIMEOUT_S = 10
TOLERANCIA_S = 60


class ProveedorNoDisponible(Exception):
    """Google no respondió o respondió con un error del servidor."""


class CodigoRechazado(Exception):
    """Google rechazó el código (vencido, reutilizado o ajeno)."""


class IdentidadNoVerificada(Exception):
    """El id_token no pasó la verificación o el correo no está verificado."""


class ProveedorGoogle(Protocol):
    def canjear_codigo(
        self, codigo: str, verificador: str, redirect_uri: str
    ) -> str: ...  # → id_token

    def llave_publica(self, id_token: str) -> Any: ...


# --------------------------------------------------------------------------- PKCE y aleatorios
def aleatorio_b64(n_bytes: int = 32) -> str:
    return secrets.token_urlsafe(n_bytes)


def desafio_pkce(verificador: str) -> str:
    """code_challenge S256 (RFC 7636 §4.2)."""
    digest = hashlib.sha256(verificador.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def url_autorizacion(
    client_id: str, redirect_uri: str, state: str, nonce: str, verificador: str
) -> str:
    parametros = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": ALCANCE,
        "state": state,
        "nonce": nonce,
        "code_challenge": desafio_pkce(verificador),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{AUTORIZACION_URL}?{urllib.parse.urlencode(parametros)}"


# --------------------------------------------------------------------------- verificación
@dataclass(frozen=True)
class Identidad:
    correo: str  # en minúsculas


def verificar_id_token(id_token: str, llave: Any, client_id: str, nonce: str) -> Identidad:
    """exp/iat se validan contra el reloj real (son de Google, no del reloj de la API)."""
    try:
        claims = jwt.decode(
            id_token,
            key=llave,
            algorithms=["RS256"],
            audience=client_id,
            issuer=EMISORES,
            leeway=TOLERANCIA_S,
            options={"require": ["iss", "aud", "exp", "iat", "sub", "email", "nonce"]},
        )
    except jwt.PyJWTError:
        raise IdentidadNoVerificada from None
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise IdentidadNoVerificada
    if claims.get("email_verified") is not True:
        raise IdentidadNoVerificada
    correo = str(claims["email"]).strip().lower()
    if not correo or len(correo) > 254:
        raise IdentidadNoVerificada
    return Identidad(correo=correo)


# --------------------------------------------------------------------------- cliente real
class GoogleReal:
    """Cliente de producción: canje por urllib y llaves públicas con caché (PyJWKClient)."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._jwks = jwt.PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600, timeout=TIMEOUT_S)

    def canjear_codigo(self, codigo: str, verificador: str, redirect_uri: str) -> str:
        datos = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": codigo,
                "code_verifier": verificador,
                "redirect_uri": redirect_uri,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
        ).encode("ascii")
        peticion = urllib.request.Request(  # noqa: S310 (URL fija https)
            TOKEN_URL,
            data=datos,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(peticion, timeout=TIMEOUT_S) as r:  # noqa: S310
                cuerpo = json.loads(r.read(65536))
        except urllib.error.HTTPError as exc:
            # 4xx: código inválido, vencido o reutilizado. 5xx: Google no disponible.
            if 400 <= exc.code < 500:
                raise CodigoRechazado from None
            raise ProveedorNoDisponible from None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            raise ProveedorNoDisponible from None
        id_token = cuerpo.get("id_token") if isinstance(cuerpo, dict) else None
        if not isinstance(id_token, str):
            raise ProveedorNoDisponible
        return id_token

    def llave_publica(self, id_token: str) -> Any:
        try:
            return self._jwks.get_signing_key_from_jwt(id_token).key
        except jwt.PyJWKClientConnectionError:
            raise ProveedorNoDisponible from None
        except jwt.PyJWTError:
            raise IdentidadNoVerificada from None
