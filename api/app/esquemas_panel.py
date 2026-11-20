"""Esquemas de entrada de la API del panel (I-7; contrato 07 §7.2).

Tipos estrictos y `extra="forbid"`: un campo desconocido o de otro tipo es 400. Los rangos y
catálogos se validan en el servicio (422 `validacion` con el campo, nunca con el valor).
"""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EntradaInvitacion(_Entrada):
    nombre_mostrar: StrictStr
    adultos: StrictInt
    ninos_autorizados: StrictInt = 0
    infantes: StrictInt = 0
    lado: StrictStr | None = None
    grupo: StrictStr | None = None
    roles: list[StrictStr] = Field(default_factory=list, max_length=13)
    mesa: StrictInt | None = None
    nota_interna: StrictStr | None = None
    no_planner: StrictInt | None = None
    telefono_principal: StrictStr | None = None
    contacto_alterno_nombre: StrictStr | None = None
    contacto_alterno_tel: StrictStr | None = None


class EntradaEdicion(_Entrada):
    """Edición parcial: solo cuentan los campos enviados (`model_fields_set`)."""

    nombre_mostrar: StrictStr | None = None
    adultos: StrictInt | None = None
    ninos_autorizados: StrictInt | None = None
    infantes: StrictInt | None = None
    lado: StrictStr | None = None
    grupo: StrictStr | None = None
    roles: list[StrictStr] | None = Field(default=None, max_length=13)
    mesa: StrictInt | None = None
    nota_interna: StrictStr | None = None
    no_planner: StrictInt | None = None
    telefono_principal: StrictStr | None = None
    contacto_alterno_nombre: StrictStr | None = None
    contacto_alterno_tel: StrictStr | None = None


class EntradaDesbloqueo(_Entrada):
    # ISO 8601 con zona (llega como texto en el JSON; por eso no es estricto).
    hasta: AwareDatetime = Field(strict=False)


class EntradaRespuestaAdmin(_Entrada):
    asiste: StrictBool
    confirmados: StrictInt
    alergias: StrictStr | None = None
    mensaje: StrictStr | None = None


class EntradaEnlaceEnviado(_Entrada):
    origen: Literal["whatsapp", "manual"]


class EntradaRecordatorio(_Entrada):
    destino: Literal["principal", "alterno"]
