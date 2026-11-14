"""Configuración leída solo de variables de entorno (sin valores secretos por defecto)."""

import re
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROLE_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, extra="ignore")

    log_level: str = "INFO"
    invitation_origin: str = "http://localhost:8080"

    # Conexión del usuario de ejecución (solo datos).
    database_url: str | None = None
    # Conexión del usuario de migraciones (dueño del esquema). Solo para `migrate`.
    migration_database_url: str | None = None
    # Rol de ejecución al que la migración otorga permisos (ADR 0019).
    db_runtime_role: str = "ma_app"

    @field_validator("db_runtime_role")
    @classmethod
    def _valid_role(cls, value: str) -> str:
        if not _ROLE_RE.fullmatch(value):
            raise ValueError("db_runtime_role debe ser un identificador simple de Postgres")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
