"""Configuración leída solo de variables de entorno (sin valores secretos por defecto)."""

import re
from functools import lru_cache
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from app.tokens import Llaves

_ROLE_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_HOSTS_LOCALES = {"localhost", "127.0.0.1"}


def validar_origen(valor: str) -> str:
    """Origen puro (esquema + host[:puerto]); https salvo localhost/127.0.0.1.

    Es la base del enlace https://<dominio>/#t=<token> (ADR 0013, doc 11).
    """
    try:
        partes = urlsplit(valor)
        puerto_ok = partes.port is None or 0 < partes.port < 65536
    except ValueError:
        raise ValueError("INVITATION_ORIGIN no es una URL válida") from None
    if (
        partes.scheme not in {"http", "https"}
        or not partes.hostname
        or partes.username
        or partes.password
        or partes.path
        or partes.query
        or partes.fragment
        or valor.endswith(("/", "?", "#"))
        or not puerto_ok
    ):
        raise ValueError(
            "INVITATION_ORIGIN debe ser solo esquema y host, p. ej. https://ejemplo.mx "
            "(sin ruta, consulta, fragmento ni '/' final)"
        )
    if partes.scheme != "https" and partes.hostname not in _HOSTS_LOCALES:
        raise ValueError("INVITATION_ORIGIN debe usar https (salvo localhost o 127.0.0.1)")
    return valor


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, extra="ignore")

    log_level: str = "INFO"
    # Origen de la invitación: CORS de la API pública y base del enlace /#t= (doc 11).
    invitation_origin: str = "http://localhost:8080"

    # Conexión del usuario de ejecución (solo datos).
    database_url: str | None = None
    # Conexión del usuario de migraciones (dueño del esquema). Solo para `migrate`.
    migration_database_url: str | None = None
    # Rol de ejecución al que la migración otorga permisos (ADR 0019).
    db_runtime_role: str = "ma_app"

    # Llaves de tokens (ADR 0019). SecretStr: no aparecen en repr ni en logs.
    token_hash_key: SecretStr | None = None
    token_hash_key_previous: SecretStr | None = None  # solo durante una rotación
    token_encryption_keys: SecretStr | None = None  # "id:llave,id:llave"; la primera es la actual

    @field_validator("db_runtime_role")
    @classmethod
    def _valid_role(cls, value: str) -> str:
        if not _ROLE_RE.fullmatch(value):
            raise ValueError("db_runtime_role debe ser un identificador simple de Postgres")
        return value

    @field_validator("invitation_origin")
    @classmethod
    def _valid_origin(cls, value: str) -> str:
        return validar_origen(value)

    def llaves(self) -> "Llaves":
        from app.tokens import parsear_llaves

        def plano(s: SecretStr | None) -> str | None:
            return s.get_secret_value() if s else None

        return parsear_llaves(
            plano(self.token_hash_key),
            plano(self.token_hash_key_previous),
            plano(self.token_encryption_keys),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
