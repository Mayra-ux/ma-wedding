"""Respaldo cifrado, restauración y verificación (I-10; doc 10, ADR 0010, 0019 y 0030).

Respaldo (`backup`, diario):
1. Abre una transacción REPEATABLE READ, exporta su instantánea y cuenta las filas por tabla.
2. `pg_dump --snapshot` vuelca EXACTAMENTE esa instantánea (los conteos cuadran con el volcado).
3. `age` lo cifra hacia la llave PÚBLICA (`BACKUP_AGE_RECIPIENT`). El volcado en claro nunca
   se escribe en disco y nunca sale del contenedor.
4. Sube `vence-AAAA-MM-DD/ma-wedding-<UTC>.dump.age` y su informe `.json` (solo conteos).
   El prefijo es la fecha de vencimiento (F7): antes de `fecha_borrado_1` vence ese día; después,
   en `fecha_borrado_2`. Desde `fecha_borrado_2` ya no se respalda.
5. Borra del destino todo lo que ya venció (además de la regla de ciclo de vida de R2).

Restauración (`restaurar`): baja el respaldo, lo descifra con la llave PRIVADA (archivo que solo
se monta para restaurar) y lo carga con `pg_restore` en una base NUEVA y vacía, con el usuario de
migraciones (dueño). Verificación (`verificar-restauracion`): ejecuta la purga primero (F9) y
compara los conteos con el informe del respaldo.

Destinos: carpeta local (`BACKUP_DIR`) o S3 compatible (`BACKUP_S3_*`; firma propia, app/s3.py).
"""

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

from app.estado import Reloj
from app.purga import InformePurga, contar_tablas, hoy_mx

PREFIJO = "vence-"
CABECERA_AGE = b"age-encryption.org/v1\n"
_CLAVE_RE = re.compile(r"^vence-(\d{4}-\d{2}-\d{2})/ma-wedding-\d{8}T\d{6}Z\.(dump\.age|json)$")


class ErrorRespaldo(RuntimeError):
    """Error con el nombre del paso; nunca lleva datos personales ni secretos."""

    def __init__(self, paso: str, detalle: str = "") -> None:
        super().__init__(f"{paso}: {detalle}" if detalle else paso)
        self.paso = paso


# ------------------------------------------------------------------------------- destinos
class Destino(Protocol):
    def subir(self, clave: str, datos: bytes) -> None: ...
    def bajar(self, clave: str) -> bytes: ...
    def borrar(self, clave: str) -> None: ...
    def listar(self, prefijo: str = "") -> list[str]: ...


class DestinoCarpeta:
    """Carpeta local (pruebas y modo «como producción»). Las claves son rutas relativas."""

    def __init__(self, base: Path) -> None:
        self.base = Path(base)

    def _ruta(self, clave: str) -> Path:
        if not _CLAVE_RE.fullmatch(clave):
            raise ErrorRespaldo("destino", "clave de respaldo inválida")
        return self.base / clave

    def subir(self, clave: str, datos: bytes) -> None:
        ruta = self._ruta(clave)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(ruta.suffix + ".parcial")
        temporal.write_bytes(datos)
        temporal.replace(ruta)  # nunca queda un respaldo a medias con el nombre final

    def bajar(self, clave: str) -> bytes:
        return self._ruta(clave).read_bytes()

    def borrar(self, clave: str) -> None:
        self._ruta(clave).unlink(missing_ok=True)

    def listar(self, prefijo: str = "") -> list[str]:
        if not self.base.exists():
            return []
        claves = [p.relative_to(self.base).as_posix() for p in self.base.rglob("*") if p.is_file()]
        return sorted(c for c in claves if c.startswith(prefijo) and _CLAVE_RE.fullmatch(c))


def destino_desde(settings) -> Destino:  # noqa: ANN001
    from app.s3 import ClienteS3, Credenciales

    s3 = settings.backup_s3_endpoint or settings.backup_s3_bucket
    if settings.backup_dir and s3:
        raise ErrorRespaldo("configuración", "usa BACKUP_DIR o BACKUP_S3_*, no ambos")
    if settings.backup_dir:
        return DestinoCarpeta(settings.backup_dir)
    if s3:
        faltan = [
            n
            for n, v in (
                ("BACKUP_S3_ENDPOINT", settings.backup_s3_endpoint),
                ("BACKUP_S3_BUCKET", settings.backup_s3_bucket),
                ("BACKUP_S3_ACCESS_KEY_ID", settings.backup_s3_access_key_id),
                ("BACKUP_S3_SECRET_ACCESS_KEY", settings.backup_s3_secret_access_key),
            )
            if not v
        ]
        if faltan:
            raise ErrorRespaldo("configuración", "faltan " + ", ".join(faltan))
        return ClienteS3(
            settings.backup_s3_endpoint,
            settings.backup_s3_bucket,
            Credenciales(
                settings.backup_s3_access_key_id.get_secret_value(),
                settings.backup_s3_secret_access_key.get_secret_value(),
                settings.backup_s3_region,
            ),
        )
    raise ErrorRespaldo("configuración", "falta el destino (BACKUP_DIR o BACKUP_S3_*)")


# ------------------------------------------------------------------------------- nombres
def vencimiento(hoy: date, f1: date, f2: date) -> date | None:
    """Fecha en que vence un respaldo tomado hoy (F7). None: ya no se respalda."""
    if hoy < f1:
        return f1
    if hoy < f2:
        return f2
    return None


def clave_respaldo(vence: date, momento: datetime) -> str:
    sello = momento.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{PREFIJO}{vence.isoformat()}/ma-wedding-{sello}.dump.age"


def clave_informe(clave: str) -> str:
    return clave.removesuffix(".dump.age") + ".json"


def vence_de(clave: str) -> date | None:
    m = _CLAVE_RE.fullmatch(clave)
    return date.fromisoformat(m.group(1)) if m else None


def vencidos(claves: list[str], hoy: date) -> list[str]:
    """Claves cuya fecha de vencimiento ya llegó (vencen al empezar ese día)."""
    return [c for c in claves if (v := vence_de(c)) is not None and hoy >= v]


# ------------------------------------------------------------------------------- herramientas
def entorno_libpq(url: str) -> dict[str, str]:
    """Entorno de libpq para pg_dump/pg_restore. La contraseña va en PGPASSWORD, nunca en la
    línea de comandos (se vería en la lista de procesos)."""
    u = make_url(url)
    env = {
        **os.environ,
        "PGHOST": u.host or "",
        "PGPORT": str(u.port or 5432),
        "PGUSER": u.username or "",
        "PGDATABASE": u.database or "",
    }
    if u.password:
        env["PGPASSWORD"] = u.password
    sslmode = u.query.get("sslmode")
    if sslmode:
        env["PGSSLMODE"] = sslmode if isinstance(sslmode, str) else sslmode[0]
    return env


def _ultima_linea(stderr: bytes) -> str:
    """Línea útil del error: la de `error:` si existe (age agrega después un aviso genérico)."""
    lineas = [ln for ln in stderr.decode("utf-8", "replace").splitlines() if ln.strip()]
    errores = [ln for ln in lineas if "error:" in ln]
    return ((errores or lineas or [""])[-1])[:200]


Volcar = Callable[[str, str], bytes]  # (url, instantánea) → volcado
Cargar = Callable[[str, bytes], None]  # (url, volcado) → None
Cifrar = Callable[[bytes, str], bytes]  # (datos, llave pública) → cifrado
Descifrar = Callable[[bytes, Path], bytes]  # (cifrado, archivo de identidad) → datos


def volcar_pg_dump(url: str, instantanea: str) -> bytes:
    env = entorno_libpq(url)
    p = subprocess.run(  # noqa: S603
        ["pg_dump", "--format=custom", "--no-owner", f"--snapshot={instantanea}"],  # noqa: S607
        capture_output=True,
        env=env,
        check=False,
    )
    if p.returncode != 0:
        raise ErrorRespaldo("pg_dump", _ultima_linea(p.stderr))
    return p.stdout


def cargar_pg_restore(url: str, volcado: bytes) -> None:
    env = entorno_libpq(url)
    p = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "pg_restore",
            "--no-owner",
            "--exit-on-error",
            "--single-transaction",
            "-d",
            env["PGDATABASE"],
        ],  # noqa: S607
        input=volcado,
        capture_output=True,
        env=env,
        check=False,
    )
    if p.returncode != 0:
        raise ErrorRespaldo("pg_restore", _ultima_linea(p.stderr))


def cifrar_age(datos: bytes, destinatario: str) -> bytes:
    p = subprocess.run(  # noqa: S603
        ["age", "--encrypt", "--recipient", destinatario],  # noqa: S607
        input=datos,
        capture_output=True,
        check=False,
    )
    if p.returncode != 0:
        raise ErrorRespaldo("cifrado", _ultima_linea(p.stderr))
    return p.stdout


def descifrar_age(datos: bytes, identidad: Path) -> bytes:
    p = subprocess.run(  # noqa: S603
        ["age", "--decrypt", "--identity", str(identidad)],  # noqa: S607
        input=datos,
        capture_output=True,
        check=False,
    )
    if p.returncode != 0:
        raise ErrorRespaldo("descifrado", _ultima_linea(p.stderr))
    return p.stdout


# ------------------------------------------------------------------------------- respaldo
@dataclass
class InformeRespaldo:
    hoy: date
    clave: str | None = None
    vence: date | None = None
    bytes_cifrados: int = 0
    sha256: str = ""
    conteos: dict[str, int] = field(default_factory=dict)
    migracion: str = ""
    borrados: list[str] = field(default_factory=list)

    def texto(self) -> str:
        if not self.clave:
            return (
                f"backup {self.hoy.isoformat()} · sin respaldo: ya pasó el borrado final · "
                f"vencidos borrados {len(self.borrados)}"
            )
        cuentas = " · ".join(f"{k} {v}" for k, v in self.conteos.items())
        return (
            f"backup {self.hoy.isoformat()} · {self.clave} · vence {self.vence} · "
            f"{self.bytes_cifrados} bytes · migración {self.migracion} · {cuentas} · "
            f"vencidos borrados {len(self.borrados)}"
        )

    def json(self) -> bytes:
        return json.dumps(
            {
                "clave": self.clave,
                "vence": self.vence.isoformat() if self.vence else None,
                "hoy": self.hoy.isoformat(),
                "bytes_cifrados": self.bytes_cifrados,
                "sha256": self.sha256,
                "migracion": self.migracion,
                "conteos": self.conteos,
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")


def limpiar(destino: Destino, hoy: date) -> list[str]:
    borrar = vencidos(destino.listar(PREFIJO), hoy)
    for clave in borrar:
        destino.borrar(clave)
    return borrar


def respaldar(
    engine: Engine,
    url: str,
    destino: Destino,
    destinatario: str | None,
    reloj: Reloj,
    volcar: Volcar = volcar_pg_dump,
    cifrar: Cifrar = cifrar_age,
) -> InformeRespaldo:
    if not destinatario:
        raise ErrorRespaldo("configuración", "falta BACKUP_AGE_RECIPIENT (llave pública)")
    momento = reloj()
    informe = InformeRespaldo(hoy=hoy_mx(reloj))
    try:
        conn = engine.connect()
    except Exception as exc:  # noqa: BLE001  (se reporta el paso sin detalles de conexión)
        raise ErrorRespaldo("conexión", type(exc).__name__) from None
    with conn:
        conn.execution_options(isolation_level="REPEATABLE READ")
        trans = conn.begin()
        try:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            f1, f2 = conn.execute(
                text("SELECT fecha_borrado_1, fecha_borrado_2 FROM configuracion_evento")
            ).one()
            informe.vence = vencimiento(informe.hoy, f1, f2)
            if informe.vence is not None:
                instantanea = conn.execute(text("SELECT pg_export_snapshot()")).scalar_one()
                from sqlalchemy.orm import Session

                with Session(bind=conn) as s:
                    informe.conteos = contar_tablas(s)
                informe.migracion = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                volcado = volcar(url, instantanea)
        finally:
            trans.rollback()  # solo lectura: nada que confirmar
    if informe.vence is not None:
        if not volcado.startswith(b"PGDMP"):
            raise ErrorRespaldo("pg_dump", "el volcado no tiene el formato esperado")
        cifrado = cifrar(volcado, destinatario)
        del volcado
        if not cifrado.startswith(CABECERA_AGE):
            raise ErrorRespaldo("cifrado", "la salida no es un archivo de age")
        informe.clave = clave_respaldo(informe.vence, momento)
        informe.bytes_cifrados = len(cifrado)
        informe.sha256 = hashlib.sha256(cifrado).hexdigest()
        try:
            destino.subir(informe.clave, cifrado)
            destino.subir(clave_informe(informe.clave), informe.json())
        except ErrorRespaldo:
            raise
        except Exception as exc:  # noqa: BLE001  (S3 o disco: se reporta el paso)
            raise ErrorRespaldo("subida", str(exc)[:200]) from None
    try:
        informe.borrados = limpiar(destino, informe.hoy)
    except Exception as exc:  # noqa: BLE001
        raise ErrorRespaldo("limpieza", str(exc)[:200]) from None
    return informe


# ------------------------------------------------------------------------------- restauración
def restaurar(
    engine_migraciones: Engine,
    url_migraciones: str,
    destino: Destino,
    clave: str,
    identidad: Path,
    descifrar: Descifrar = descifrar_age,
    cargar: Cargar = cargar_pg_restore,
) -> None:
    """Carga un respaldo en una base NUEVA y vacía (no pisa una base con datos)."""
    with engine_migraciones.connect() as conn:
        tablas = conn.execute(
            text("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'")
        ).scalar_one()
    if tablas:
        raise ErrorRespaldo("restauración", "la base de destino no está vacía")
    cifrado = destino.bajar(clave)
    informe = json.loads(destino.bajar(clave_informe(clave)))
    if hashlib.sha256(cifrado).hexdigest() != informe["sha256"]:
        raise ErrorRespaldo("restauración", "el respaldo no coincide con su informe (sha256)")
    cargar(url_migraciones, descifrar(cifrado, identidad))


@dataclass
class InformeVerificacion:
    purga: InformePurga
    esperado: dict[str, int]
    obtenido: dict[str, int]
    migracion_esperada: str
    migracion_obtenida: str

    @property
    def correcta(self) -> bool:
        return self.esperado == self.obtenido and self.migracion_esperada == self.migracion_obtenida

    def texto(self) -> str:
        diferencias = {
            k: (self.esperado.get(k), self.obtenido.get(k))
            for k in sorted(set(self.esperado) | set(self.obtenido))
            if self.esperado.get(k) != self.obtenido.get(k)
        }
        estado = "conteos coinciden" if self.correcta else f"DIFERENCIAS {diferencias}"
        return (
            f"verificar-restauracion · purga: {self.purga.fase} ({self.purga.cambios} cambios) · "
            f"migración {self.migracion_obtenida} · {estado}"
        )


def esperado_tras_purga(conteos: dict[str, int], purga: InformePurga) -> dict[str, int]:
    """Lo que debe quedar después de la purga (F9) a partir de los conteos del respaldo."""
    esperado = dict(conteos)
    if purga.hoy >= purga.fecha_borrado_1:
        esperado["telefonos"] = 0
        esperado["alergias"] = 0
    if purga.hoy >= purga.fecha_borrado_2:
        esperado = {k: 0 for k in esperado}
    if purga.cambios:
        esperado["evento_auditoria"] = esperado.get("evento_auditoria", 0) + 1
    return esperado


def verificar_restauracion(
    engine: Engine, informe_respaldo: dict, reloj: Reloj
) -> InformeVerificacion:
    from sqlalchemy.orm import Session

    from app.purga import purgar

    with Session(engine) as s, s.begin():
        purga = purgar(s, reloj)
    with Session(engine) as s:
        obtenido = contar_tablas(s)
        migracion = s.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        # La API puede leer la configuración del evento con el usuario de ejecución.
        s.execute(text("SELECT cierre_plazo FROM configuracion_evento WHERE id = 1")).one()
    return InformeVerificacion(
        purga=purga,
        esperado=esperado_tras_purga(informe_respaldo["conteos"], purga),
        obtenido=obtenido,
        migracion_esperada=informe_respaldo["migracion"],
        migracion_obtenida=migracion,
    )
