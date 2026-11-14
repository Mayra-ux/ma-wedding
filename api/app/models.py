"""Modelos ORM. La fuente de verdad de las restricciones es la migración (la DB)."""

from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NOW = text("now()")


class Base(DeclarativeBase):
    pass


class ConfiguracionEvento(Base):
    __tablename__ = "configuracion_evento"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    cierre_plazo: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    congelamiento: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_borrado_1: Mapped[date] = mapped_column(Date)
    fecha_borrado_2: Mapped[date] = mapped_column(Date)


class Invitacion(Base):
    __tablename__ = "invitacion"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(Text)
    no_planner: Mapped[int | None] = mapped_column(Integer)
    nombre_mostrar: Mapped[str] = mapped_column(String(120))
    adultos: Mapped[int] = mapped_column(Integer)
    ninos_autorizados: Mapped[int] = mapped_column(Integer, default=0)
    infantes: Mapped[int] = mapped_column(Integer, default=0)
    pases: Mapped[int] = mapped_column(Integer, Computed("adultos + ninos_autorizados"))
    pases_planner_original: Mapped[int | None] = mapped_column(Integer)
    lado: Mapped[str | None] = mapped_column(Text)
    grupo: Mapped[str | None] = mapped_column(Text)
    mesa: Mapped[int | None] = mapped_column(Integer)
    nota_interna: Mapped[str | None] = mapped_column(String(500))
    telefono_principal: Mapped[str | None] = mapped_column(Text)
    contacto_alterno_nombre: Mapped[str | None] = mapped_column(String(120))
    contacto_alterno_tel: Mapped[str | None] = mapped_column(Text)
    requiere_revision: Mapped[bool] = mapped_column(Boolean, default=False)
    motivos_revision: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    desbloqueada_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enlace_enviado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enlace_enviado_origen: Mapped[str | None] = mapped_column(Text)
    archivada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    actualizada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class InvitacionRol(Base):
    __tablename__ = "invitacion_rol"

    invitacion_id: Mapped[int] = mapped_column(ForeignKey("invitacion.id"), primary_key=True)
    rol: Mapped[str] = mapped_column(Text, primary_key=True)


class VersionRespuesta(Base):
    __tablename__ = "version_respuesta"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    invitacion_id: Mapped[int] = mapped_column(ForeignKey("invitacion.id"))
    numero: Mapped[int] = mapped_column(Integer)
    vigente: Mapped[bool] = mapped_column(Boolean)
    asiste: Mapped[bool] = mapped_column(Boolean)
    confirmados: Mapped[int] = mapped_column(Integer)
    alergias: Mapped[str | None] = mapped_column(String(200))
    mensaje: Mapped[str | None] = mapped_column(String(500))
    origen: Mapped[str] = mapped_column(Text)
    actor: Mapped[str | None] = mapped_column(String(254))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)


class Enlace(Base):
    __tablename__ = "enlace"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    invitacion_id: Mapped[int] = mapped_column(ForeignKey("invitacion.id"))
    hmac_token: Mapped[bytes] = mapped_column(LargeBinary)
    token_cifrado: Mapped[bytes] = mapped_column(LargeBinary)
    id_llave: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    revocado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SesionAdmin(Base):
    __tablename__ = "sesion_admin"

    hash_sesion: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    correo: Mapped[str] = mapped_column(String(254))
    secreto_csrf: Mapped[bytes] = mapped_column(LargeBinary)
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EventoAuditoria(Base):
    __tablename__ = "evento_auditoria"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor: Mapped[str] = mapped_column(String(254))
    accion: Mapped[str] = mapped_column(Text)
    codigo_invitacion: Mapped[str | None] = mapped_column(Text)
    detalle: Mapped[dict] = mapped_column(JSONB, default=dict)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
