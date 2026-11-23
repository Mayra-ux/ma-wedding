"""Respaldo sin DB (I-10; doc 10, F7): vencimientos, nombres, destinos y configuración."""

import http.server
import threading
import urllib.parse
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest

from app.config import Settings
from app.respaldo import (
    DestinoCarpeta,
    ErrorRespaldo,
    clave_informe,
    clave_respaldo,
    destino_desde,
    esperado_tras_purga,
    vencidos,
    vencimiento,
)
from app.s3 import ClienteS3, Credenciales, ErrorS3

F1, F2 = date(2027, 4, 5), date(2027, 6, 4)
RECIPIENT = "age1" + "q" * 58


@pytest.mark.parametrize(
    ("hoy", "vence"),
    [
        (date(2026, 12, 1), F1),
        (date(2027, 4, 4), F1),  # el respaldo final (con teléfonos) vence el 5 abr
        (date(2027, 4, 5), F2),
        (date(2027, 6, 3), F2),
        (date(2027, 6, 4), None),  # desde el borrado final ya no se respalda
    ],
)
def test_vencimiento_por_dato_mas_restrictivo(hoy: date, vence: date | None) -> None:
    assert vencimiento(hoy, F1, F2) == vence


def test_nombres_y_vencidos() -> None:
    clave = clave_respaldo(F1, datetime(2027, 3, 1, 8, 30, tzinfo=UTC))
    assert clave == "vence-2027-04-05/ma-wedding-20270301T083000Z.dump.age"
    assert clave_informe(clave) == "vence-2027-04-05/ma-wedding-20270301T083000Z.json"
    otra = clave_respaldo(F2, datetime(2027, 4, 10, tzinfo=UTC))
    claves = [clave, clave_informe(clave), otra, "basura.txt"]
    assert vencidos(claves, date(2027, 4, 4)) == []
    assert vencidos(claves, F1) == [clave, clave_informe(clave)]
    assert vencidos(claves, F2) == [clave, clave_informe(clave), otra]


def test_destino_carpeta(tmp_path) -> None:  # noqa: ANN001
    d = DestinoCarpeta(tmp_path)
    clave = clave_respaldo(F1, datetime(2027, 1, 1, tzinfo=UTC))
    d.subir(clave, b"age-encryption.org/v1\nxx")
    assert d.listar() == [clave] and d.bajar(clave).startswith(b"age-")
    assert not list(tmp_path.rglob("*.parcial"))
    d.borrar(clave)
    assert d.listar() == []
    with pytest.raises(ErrorRespaldo):
        d.subir("../fuera.dump.age", b"x")  # nunca escribe fuera de la carpeta


def test_configuracion_del_destino(tmp_path) -> None:  # noqa: ANN001
    assert Settings(backup_dir="").backup_dir is None  # vacía = sin carpeta
    assert isinstance(destino_desde(Settings(backup_dir=tmp_path)), DestinoCarpeta)
    with pytest.raises(ErrorRespaldo, match="falta el destino"):
        destino_desde(Settings())
    with pytest.raises(ErrorRespaldo, match="no ambos"):
        destino_desde(Settings(backup_dir=tmp_path, backup_s3_bucket="b"))
    with pytest.raises(ErrorRespaldo, match="BACKUP_S3_ACCESS_KEY_ID"):
        destino_desde(
            Settings(backup_s3_endpoint="https://s3.ejemplo.invalid", backup_s3_bucket="b")
        )


@pytest.mark.parametrize(
    "endpoint",
    ["http://s3.ejemplo.invalid", "https://s3.ejemplo.invalid/ruta", "ftp://x"],
)
def test_endpoint_https_salvo_local(endpoint: str) -> None:
    with pytest.raises(ValueError):
        Settings(backup_s3_endpoint=endpoint)


def test_endpoint_local_de_pruebas() -> None:
    assert Settings(backup_s3_endpoint="http://s3-prueba:7070").backup_s3_endpoint
    assert Settings(backup_s3_endpoint="http://127.0.0.1:7070").backup_s3_endpoint


@pytest.mark.parametrize("valor", ["age1corta", "AGE1" + "Q" * 58, "ssh-ed25519 AAAA"])
def test_llave_publica_de_age(valor: str) -> None:
    with pytest.raises(ValueError, match="age"):
        Settings(backup_age_recipient=valor)
    assert Settings(backup_age_recipient=RECIPIENT).backup_age_recipient == RECIPIENT


def test_esperado_tras_purga() -> None:
    from app.purga import InformePurga

    conteos = {"invitacion": 3, "telefonos": 2, "alergias": 1, "evento_auditoria": 5}
    nada = InformePurga(hoy=date(2027, 3, 1), fecha_borrado_1=F1, fecha_borrado_2=F2)
    assert esperado_tras_purga(conteos, nada) == conteos
    abril = InformePurga(hoy=F1, fecha_borrado_1=F1, fecha_borrado_2=F2, telefonos=2, alergias=1)
    assert esperado_tras_purga(conteos, abril) == conteos | {
        "telefonos": 0,
        "alergias": 0,
        "evento_auditoria": 6,
    }
    junio = InformePurga(hoy=F2, fecha_borrado_1=F1, fecha_borrado_2=F2, invitaciones=3)
    assert esperado_tras_purga(conteos, junio) == {
        "invitacion": 0,
        "telefonos": 0,
        "alergias": 0,
        "evento_auditoria": 1,
    }


# --------------------------------------------------------------------- S3 simulado (protocolo)
class _S3(http.server.BaseHTTPRequestHandler):
    """S3 mínimo en memoria: PUT, GET, DELETE y ListObjectsV2 con estilo ruta. Exige firma."""

    objetos: dict[str, bytes] = {}

    def _clave(self) -> tuple[str, str, dict]:
        partes = urllib.parse.urlsplit(self.path)
        _, bucket, *resto = partes.path.split("/", 2)
        return (
            bucket,
            urllib.parse.unquote(resto[0]) if resto else "",
            dict(urllib.parse.parse_qsl(partes.query)),
        )

    def _autorizada(self) -> bool:
        auth = self.headers.get("authorization", "")
        ok = auth.startswith("AWS4-HMAC-SHA256 Credential=FICTICIA/") and self.headers.get(
            "x-amz-content-sha256"
        )
        if not ok:
            self.rfile.read(int(self.headers.get("content-length") or 0))  # vacía el cuerpo
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"<Error><Code>AccessDenied</Code></Error>")
        return bool(ok)

    def do_PUT(self) -> None:  # noqa: N802
        if self._autorizada():
            _, clave, _ = self._clave()
            self.objetos[clave] = self.rfile.read(int(self.headers["content-length"]))
            self.send_response(200)
            self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._autorizada():
            return
        _, clave, q = self._clave()
        if clave:
            if clave not in self.objetos:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"<Error><Code>NoSuchKey</Code></Error>")
                return
            cuerpo = self.objetos[clave]
        else:  # ListObjectsV2 paginado de 2 en 2 para probar la continuación
            claves = sorted(k for k in self.objetos if k.startswith(q.get("prefix", "")))
            inicio = int(q.get("continuation-token") or 0)
            pagina = claves[inicio : inicio + 2]
            truncado = inicio + 2 < len(claves)
            ns = "http://s3.amazonaws.com/doc/2006-03-01/"
            cuerpo = (
                f'<ListBucketResult xmlns="{ns}"><IsTruncated>{str(truncado).lower()}</IsTruncated>'
                + "".join(f"<Contents><Key>{k}</Key></Contents>" for k in pagina)
                + (
                    f"<NextContinuationToken>{inicio + 2}</NextContinuationToken>"
                    if truncado
                    else ""
                )
                + "</ListBucketResult>"
            ).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_DELETE(self) -> None:  # noqa: N802
        if self._autorizada():
            _, clave, _ = self._clave()
            self.objetos.pop(clave, None)
            self.send_response(204)
            self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def s3() -> Iterator[ClienteS3]:
    manejador = type("S3", (_S3,), {"objetos": {}})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    cliente = ClienteS3(
        f"http://127.0.0.1:{srv.server_port}", "respaldos", Credenciales("FICTICIA", "secreta")
    )
    cliente.objetos = manejador.objetos
    yield cliente
    srv.shutdown()


def test_cliente_s3_subir_listar_bajar_borrar(s3) -> None:  # noqa: ANN001
    claves = [clave_respaldo(F1, datetime(2027, 1, d, tzinfo=UTC)) for d in range(1, 6)]
    for c in claves:
        s3.subir(c, c.encode())
    assert s3.listar("vence-") == sorted(claves)  # 5 claves en 3 páginas
    assert s3.bajar(claves[0]) == claves[0].encode()
    s3.borrar(claves[0])
    assert claves[0] not in s3.listar()
    with pytest.raises(ErrorS3, match="404 NoSuchKey"):
        s3.bajar(claves[0])


def test_cliente_s3_credenciales_rechazadas(s3) -> None:  # noqa: ANN001
    malo = ClienteS3(f"http://{s3.host}", "respaldos", Credenciales("OTRA", "x"))
    with pytest.raises(ErrorS3, match="403 AccessDenied") as info:
        malo.subir("vence-2027-04-05/ma-wedding-20270101T000000Z.json", b"{}")
    assert "x" not in str(info.value).split("403")[0]  # sin secretos en el error
