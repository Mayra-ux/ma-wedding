"""Cliente S3 mínimo con firma AWS Signature Version 4, solo con la biblioteca estándar.

ADR 0030: sin dependencias nuevas (ni boto3). Cubre lo que necesita el respaldo: subir, bajar,
listar por prefijo y borrar objetos, con direcciones de estilo ruta (`<endpoint>/<bucket>/<clave>`),
que aceptan Cloudflare R2 y los servidores S3 compatibles. La firma se prueba con los ejemplos
oficiales de la documentación de AWS (tests/test_s3_firma.py).
"""

import contextlib
import hashlib
import hmac
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from defusedxml import ElementTree

VACIO = hashlib.sha256(b"").hexdigest()
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


def _hmac(llave: bytes, mensaje: str) -> bytes:
    return hmac.new(llave, mensaje.encode("utf-8"), hashlib.sha256).digest()


def codificar(valor: str, conservar_diagonal: bool = False) -> str:
    """URI-encode de SigV4: todo salvo A-Z a-z 0-9 - _ . ~ (y '/' en rutas)."""
    return urllib.parse.quote(valor, safe="-_.~" + ("/" if conservar_diagonal else ""))


@dataclass(frozen=True)
class Credenciales:
    llave_acceso: str
    llave_secreta: str
    region: str = "auto"
    servicio: str = "s3"


def firmar(
    cred: Credenciales,
    metodo: str,
    ruta: str,
    consulta: dict[str, str],
    encabezados: dict[str, str],
    hash_cuerpo: str,
    momento: datetime,
) -> dict[str, str]:
    """Devuelve los encabezados a enviar, con `Authorization` y `x-amz-date`.

    `encabezados` debe incluir `host`; todos los que se pasen se firman.
    """
    amz_fecha = momento.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    dia = amz_fecha[:8]
    todos = {k.lower().strip(): " ".join(str(v).split()) for k, v in encabezados.items()}
    todos["x-amz-date"] = amz_fecha
    nombres = sorted(todos)
    canonicos = "".join(f"{k}:{todos[k]}\n" for k in nombres)
    firmados = ";".join(nombres)
    consulta_canonica = "&".join(
        f"{codificar(k)}={codificar(v)}" for k, v in sorted(consulta.items())
    )
    peticion_canonica = "\n".join(
        [
            metodo,
            codificar(ruta, conservar_diagonal=True),
            consulta_canonica,
            canonicos,
            firmados,
            hash_cuerpo,
        ]
    )
    alcance = f"{dia}/{cred.region}/{cred.servicio}/aws4_request"
    a_firmar = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_fecha,
            alcance,
            hashlib.sha256(peticion_canonica.encode("utf-8")).hexdigest(),
        ]
    )
    llave = _hmac(("AWS4" + cred.llave_secreta).encode("utf-8"), dia)
    for parte in (cred.region, cred.servicio, "aws4_request"):
        llave = _hmac(llave, parte)
    firma = hmac.new(llave, a_firmar.encode("utf-8"), hashlib.sha256).hexdigest()
    todos["authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={cred.llave_acceso}/{alcance}, "
        f"SignedHeaders={firmados}, Signature={firma}"
    )
    return todos


class ErrorS3(RuntimeError):
    """Error de S3 sin datos sensibles (solo método, estado y código de S3)."""


Abrir = Callable[..., object]


class ClienteS3:
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        cred: Credenciales,
        abrir: Abrir = urllib.request.urlopen,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        partes = urllib.parse.urlsplit(endpoint)
        self.esquema = partes.scheme
        self.host = partes.netloc
        self.bucket = bucket
        self.cred = cred
        self._abrir = abrir
        self._reloj = reloj

    def _pedir(
        self,
        metodo: str,
        clave: str = "",
        consulta: dict[str, str] | None = None,
        cuerpo: bytes = b"",
    ) -> bytes:
        consulta = consulta or {}
        ruta = f"/{self.bucket}" + (f"/{clave}" if clave else "")
        hash_cuerpo = hashlib.sha256(cuerpo).hexdigest() if cuerpo else VACIO
        encabezados = firmar(
            self.cred,
            metodo,
            ruta,
            consulta,
            {"host": self.host, "x-amz-content-sha256": hash_cuerpo},
            hash_cuerpo,
            self._reloj(),
        )
        encabezados.pop("host")
        url = f"{self.esquema}://{self.host}{codificar(ruta, conservar_diagonal=True)}"
        if consulta:
            url += "?" + "&".join(
                f"{codificar(k)}={codificar(v)}" for k, v in sorted(consulta.items())
            )
        peticion = urllib.request.Request(  # noqa: S310  (endpoint validado en config)
            url, data=cuerpo if metodo == "PUT" else None, method=metodo, headers=encabezados
        )
        try:
            with self._abrir(peticion, timeout=60) as respuesta:
                return respuesta.read()
        except urllib.error.HTTPError as exc:
            codigo = ""
            with contextlib.suppress(Exception):  # cuerpo de error que no es XML de S3
                codigo = ElementTree.fromstring(exc.read()).findtext("Code") or ""
            raise ErrorS3(f"S3 {metodo} respondió {exc.code} {codigo}".strip()) from None
        except urllib.error.URLError as exc:
            raise ErrorS3(f"S3 {metodo}: sin conexión ({type(exc.reason).__name__})") from None
        except OSError as exc:  # conexión cortada a la mitad
            raise ErrorS3(f"S3 {metodo}: sin conexión ({type(exc).__name__})") from None

    def subir(self, clave: str, datos: bytes) -> None:
        self._pedir("PUT", clave, cuerpo=datos)

    def bajar(self, clave: str) -> bytes:
        return self._pedir("GET", clave)

    def borrar(self, clave: str) -> None:
        self._pedir("DELETE", clave)

    def listar(self, prefijo: str = "") -> list[str]:
        claves: list[str] = []
        consulta = {"list-type": "2", "prefix": prefijo}
        while True:
            raiz = ElementTree.fromstring(self._pedir("GET", consulta=consulta))
            ns = NS if raiz.tag.startswith(NS) else ""
            claves += [c.findtext(f"{ns}Key") or "" for c in raiz.findall(f"{ns}Contents")]
            if (raiz.findtext(f"{ns}IsTruncated") or "").lower() != "true":
                return [c for c in claves if c]
            consulta = {
                **consulta,
                "continuation-token": raiz.findtext(f"{ns}NextContinuationToken") or "",
            }
