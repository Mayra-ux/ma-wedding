"""Esquemas de la API pública (contrato 07, §7.1).

Entrada: tipos estrictos y `extra="forbid"`; el invitado no puede enviar pases, nombres ni
niños (regla B3). Salida: solo lo que el contrato permite; nunca código INV, IDs, teléfonos,
categorías, mesa ni nota.
"""

import unicodedata
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr

from app.errores import ErrorAPI

MAX_ALERGIAS = 200
MAX_MENSAJE = 500


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EntradaConsulta(_Entrada):
    token: StrictStr


class EntradaRespuesta(_Entrada):
    token: StrictStr
    asiste: StrictBool
    confirmados: StrictInt
    alergias: StrictStr | None = None
    mensaje: StrictStr | None = None


class _Salida(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RespuestaPublica(_Salida):
    asiste: bool
    confirmados: int
    alergias: str | None
    mensaje: str | None
    actualizada: str  # ISO 8601 con zona −06:00


class ConsultaPublica(_Salida):
    nombre_mostrar: str
    pases: int
    fecha_limite: str  # instante exacto del cierre global, ISO 8601 con zona
    fecha_limite_mostrar: date  # último día local para responder (AAAA-MM-DD)
    estado: Literal["abierta", "cerrada", "congelada"]
    abierta_hasta: str | None
    respuesta: RespuestaPublica | None


class RespuestaGuardada(_Salida):
    respuesta: RespuestaPublica


# --------------------------------------------------------------------------- textos libres
_PERMITIDOS = {"\n", "\t"}


def normalizar_texto(valor: str | None, campo: str, maximo: int) -> str | None:
    """Normaliza un texto libre del invitado y lo valida (422 `validacion` si no cumple).

    - "\\r\\n" → "\\n"; se quitan espacios al inicio y al final; vacío → None.
    - Rechaza caracteres de control (categoría Unicode Cc) salvo salto de línea y tabulador.
    - La longitud se cuenta en caracteres, igual que `varchar(n)` en la DB.
    """
    if valor is None:
        return None
    texto = valor.replace("\r\n", "\n").strip()
    if not texto:
        return None
    if any(unicodedata.category(c) == "Cc" and c not in _PERMITIDOS for c in texto):
        raise ErrorAPI(422, "validacion", {campo: "caracteres_no_permitidos"})
    if len(texto) > maximo:
        raise ErrorAPI(422, "validacion", {campo: "demasiado_largo"})
    return texto
