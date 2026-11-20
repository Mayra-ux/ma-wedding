"""Google simulado para las pruebas (I-6): nunca usa la red.

Firma id_tokens RS256 con una llave RSA generada en memoria. Cada código de autorización se
asocia a unos claims; `canjear_codigo` devuelve el id_token firmado. Todo es ficticio.
"""

import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app.google import CodigoRechazado, ProveedorNoDisponible

CLIENT_ID = "cliente-prueba.apps.googleusercontent.com"


def llave_rsa() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class GoogleSimulado:
    def __init__(self, client_id: str = CLIENT_ID) -> None:
        self.client_id = client_id
        self.llave = llave_rsa()
        self.codigos: dict[str, dict[str, Any]] = {}
        self.canjes: list[tuple[str, str, str]] = []  # (código, verificador, redirect_uri)
        self.falla: type[Exception] | None = None  # CodigoRechazado o ProveedorNoDisponible
        self.llave_firma: rsa.RSAPrivateKey | None = None  # para firmar con otra llave

    def claims(self, correo: str, nonce: str, /, **extra: Any) -> dict[str, Any]:
        ahora = int(time.time())
        base = {
            "iss": "https://accounts.google.com",
            "aud": self.client_id,
            "sub": "1000000000000000000001",
            "email": correo,
            "email_verified": True,
            "nonce": nonce,
            "iat": ahora,
            "exp": ahora + 3600,
        }
        base.update(extra)
        return {k: v for k, v in base.items() if v is not ...}  # `...` quita un claim

    def preparar(self, codigo: str, correo: str, nonce: str, /, **extra: Any) -> None:
        self.codigos[codigo] = self.claims(correo, nonce, **extra)

    def firmar(self, claims: dict[str, Any]) -> str:
        return jwt.encode(claims, self.llave_firma or self.llave, algorithm="RS256")

    # --- ProveedorGoogle ---
    def canjear_codigo(self, codigo: str, verificador: str, redirect_uri: str) -> str:
        self.canjes.append((codigo, verificador, redirect_uri))
        if self.falla is not None:
            raise self.falla
        if codigo not in self.codigos:
            raise CodigoRechazado
        return self.firmar(self.codigos.pop(codigo))  # un código sirve una sola vez

    def llave_publica(self, id_token: str) -> Any:
        return self.llave.public_key()


__all__ = ["CLIENT_ID", "CodigoRechazado", "GoogleSimulado", "ProveedorNoDisponible"]
