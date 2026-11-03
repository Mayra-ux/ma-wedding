"""Motor y sesiones de SQLAlchemy (psycopg 3)."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import guardas  # noqa: F401  (instala la guarda contra DELETE de invitaciones)


def normalize_url(url: str) -> str:
    """Los proveedores entregan `postgresql://`; SQLAlchemy necesita el driver explícito."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(url: str) -> Engine:
    return create_engine(normalize_url(url), pool_pre_ping=True)


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
