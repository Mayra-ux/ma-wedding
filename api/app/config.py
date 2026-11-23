"""Configuración leída solo de variables de entorno (sin valores secretos por defecto)."""

import re
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from app.tokens import Llaves

_ROLE_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_HOSTS_LOCALES = {"localhost", "127.0.0.1"}
# Correo simple: suficiente para comparar con el claim `email` de Google (que ya viene validado).
_CORREO_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)+$")


def parsear_correos(valor: str, variable: str) -> frozenset[str]:
    """Lista separada por comas → conjunto en minúsculas. Nunca repite los correos en errores."""
    correos = [c.strip().lower() for c in valor.split(",") if c.strip()]
    malos = sum(1 for c in correos if len(c) > 254 or not _CORREO_RE.fullmatch(c))
    if malos:
        raise ValueError(f"{variable}: {malos} correo(s) con formato inválido")
    return frozenset(correos)


def validar_origen(valor: str) -> str:
    """Origen puro (esquema + host[:puerto]); https salvo localhost/127.0.0.1.

    Es la base del enlace https://<dominio>/#t=<token> (ADR 0013, doc 11).
    """
    try:
        partes = urlsplit(valor)
        puerto_ok = partes.port is None or 0 < partes.port < 65536
    except ValueError:
        raise ValueError("el origen no es una URL válida") from None
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
            "el origen debe ser solo esquema y host, p. ej. https://ejemplo.mx "
            "(sin ruta, consulta, fragmento ni '/' final)"
        )
    if partes.scheme != "https" and partes.hostname not in _HOSTS_LOCALES:
        raise ValueError("el origen debe usar https (salvo localhost o 127.0.0.1)")
    return valor


class Settings(BaseSettings):
    # hide_input_in_errors: un error de configuración nunca imprime valores (correos, llaves).
    model_config = SettingsConfigDict(
        env_prefix="", case_sensitive=False, extra="ignore", hide_input_in_errors=True
    )

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

    # Límites de la API pública (ADR 0019; valores iniciales configurables).
    rate_limit_token_lookup_per_hour: int = Field(20, ge=1)
    rate_limit_token_response_per_hour: int = Field(10, ge=1)
    rate_limit_ip_per_hour: int = Field(300, ge=1)
    max_body_public: int = Field(4096, ge=256)  # bytes
    # HSTS solo con el dominio definitivo (ADR 0019 y 0021).
    security_hsts: bool = False

    # --- Panel y login con Google (I-6; ADR 0005, 0015, doc 06) ---
    # Origen público de la API y del panel: base de la URI de redirección y valor esperado
    # del encabezado Origin en las escrituras del panel.
    panel_origin: str = "http://localhost:8000"
    # Carpeta con el build del panel (I-9). En la imagen: /srv/panel. Sin build → 503.
    panel_dir: Path | None = None
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    # Firma del estado de OAuth y de los identificadores de sesión (doc 11).
    session_secret: SecretStr | None = None
    # Listas de correos por rol, separadas por comas (no se exponen).
    admin_emails_novios: str = ""
    admin_emails_planner: str = ""
    sesion_inactividad_horas: float = Field(8, gt=0)
    sesion_maxima_dias: float = Field(7, gt=0)
    max_body_admin: int = Field(65536, ge=1024)  # bytes
    max_import_file: int = Field(2 * 1024 * 1024, ge=1024)  # bytes (I-8, ADR 0019)

    @field_validator("db_runtime_role")
    @classmethod
    def _valid_role(cls, value: str) -> str:
        if not _ROLE_RE.fullmatch(value):
            raise ValueError("db_runtime_role debe ser un identificador simple de Postgres")
        return value

    @field_validator("invitation_origin", "panel_origin")
    @classmethod
    def _valid_origin(cls, value: str) -> str:
        return validar_origen(value)

    @field_validator("admin_emails_novios", "admin_emails_planner")
    @classmethod
    def _valid_correos(cls, value: str, info) -> str:  # noqa: ANN001
        parsear_correos(value, info.field_name.upper())
        return value

    @model_validator(mode="after")
    def _listas_disjuntas(self) -> "Settings":
        # Un correo en las dos listas es ambiguo: la API no arranca (sin mostrar cuál).
        if self.correos_novios() & self.correos_planner():
            raise ValueError("ADMIN_EMAILS_NOVIOS y ADMIN_EMAILS_PLANNER comparten correos")
        return self

    def correos_novios(self) -> frozenset[str]:
        return parsear_correos(self.admin_emails_novios, "ADMIN_EMAILS_NOVIOS")

    def correos_planner(self) -> frozenset[str]:
        return parsear_correos(self.admin_emails_planner, "ADMIN_EMAILS_PLANNER")

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
