"""Configuración leída solo de variables de entorno (sin valores secretos por defecto)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, extra="ignore")

    log_level: str = "INFO"
    invitation_origin: str = "http://localhost:8080"


@lru_cache
def get_settings() -> Settings:
    return Settings()
