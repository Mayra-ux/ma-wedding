"""Alertas con Healthchecks (I-10; ADR 0019 y 0030), probadas con un servidor simulado local."""

import http.server
import threading
from collections.abc import Iterator

import pytest

from app.alertas import Alerta
from app.config import Settings


class _Simulado(http.server.BaseHTTPRequestHandler):
    recibidas: list[tuple[str, str]] = []
    estado = 200

    def do_POST(self) -> None:  # noqa: N802
        largo = int(self.headers.get("content-length", 0))
        type(self).recibidas.append((self.path, self.rfile.read(largo).decode("utf-8")))
        self.send_response(type(self).estado)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def healthchecks() -> Iterator[tuple[str, type[_Simulado]]]:
    manejador = type("Manejador", (_Simulado,), {"recibidas": [], "estado": 200})
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_port}/ping/0f0e0d0c-ficticio", manejador
    servidor.shutdown()


def test_sin_url_las_alertas_estan_apagadas() -> None:
    def prohibido(*a: object, **k: object) -> None:
        raise AssertionError("no debe hacer ninguna petición")

    alerta = Alerta(None, abrir=prohibido)
    assert not alerta.activa
    assert alerta.inicio() is False
    assert alerta.exito("x") is False
    assert alerta.fallo("paso") is False


def test_inicio_exito_y_fallo(healthchecks) -> None:  # noqa: ANN001
    url, srv = healthchecks
    alerta = Alerta(url)
    assert alerta.inicio() and alerta.exito("purge 2027-04-05 · telefonos 3")
    assert alerta.fallo("pg_dump", "conexión rechazada")
    assert srv.recibidas == [
        ("/ping/0f0e0d0c-ficticio/start", ""),
        ("/ping/0f0e0d0c-ficticio", "purge 2027-04-05 · telefonos 3"),
        ("/ping/0f0e0d0c-ficticio/fail", "falló: pg_dump\nconexión rechazada"),
    ]


def test_un_servidor_caido_no_tumba_la_tarea(healthchecks, caplog) -> None:  # noqa: ANN001
    url, srv = healthchecks
    srv.estado = 500
    assert Alerta(url).fallo("backup") is False
    assert Alerta("http://127.0.0.1:9/ping/x").inicio() is False  # puerto cerrado
    assert "ping" not in caplog.text and "127.0.0.1" not in caplog.text  # la URL es secreta


def test_cuerpo_acotado(healthchecks) -> None:  # noqa: ANN001
    url, srv = healthchecks
    Alerta(url).exito("x" * 50_000)
    assert len(srv.recibidas[0][1]) == 10_000


@pytest.mark.parametrize("url", ["http://hc-ping.com/abc", "ftp://x/y"])
def test_la_url_debe_ser_https(url: str) -> None:
    with pytest.raises(ValueError, match="https"):
        Settings(alert_ping_url_purge=url)


def test_url_vacia_es_apagada() -> None:
    assert Settings(alert_ping_url_backup="").alert_ping_url_backup is None


def _con_entorno(monkeypatch, **valores: str) -> None:  # noqa: ANN001
    from app.config import get_settings

    for k in ("DATABASE_URL", "BACKUP_DIR", "BACKUP_AGE_RECIPIENT", "ALERT_PING_URL_PURGE"):
        monkeypatch.delenv(k, raising=False)
    for k, v in valores.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()


def test_fallo_forzado_de_purge_genera_alerta(healthchecks, monkeypatch, capsys) -> None:  # noqa: ANN001
    from app.__main__ import main
    from app.config import get_settings

    url, srv = healthchecks
    _con_entorno(
        monkeypatch,
        DATABASE_URL="postgresql+psycopg://nadie:nada@127.0.0.1:9/ninguna?connect_timeout=2",
        ALERT_PING_URL_PURGE=url,
    )
    try:
        assert main(["purge"]) == 1
    finally:
        get_settings.cache_clear()
    assert [p for p, _ in srv.recibidas] == [
        "/ping/0f0e0d0c-ficticio/start",
        "/ping/0f0e0d0c-ficticio/fail",
    ]
    assert srv.recibidas[1][1].startswith("falló: purge")
    assert "nada" not in srv.recibidas[1][1]  # nunca la contraseña
    assert "FALLÓ" in capsys.readouterr().err


def test_fallo_forzado_de_backup_genera_alerta(healthchecks, monkeypatch, tmp_path) -> None:  # noqa: ANN001
    from app.__main__ import main
    from app.config import get_settings

    url, srv = healthchecks
    monkeypatch.setenv("ALERT_PING_URL_BACKUP", url)
    _con_entorno(
        monkeypatch,
        DATABASE_URL="postgresql+psycopg://nadie:nada@127.0.0.1:9/ninguna?connect_timeout=2",
        BACKUP_DIR=str(tmp_path),
        BACKUP_AGE_RECIPIENT="age1" + "q" * 58,
    )
    try:
        assert main(["backup"]) == 1
    finally:
        get_settings.cache_clear()
    assert srv.recibidas[-1][0].endswith("/fail")
    assert srv.recibidas[-1][1].startswith("falló: conexión")
    assert list(tmp_path.iterdir()) == []  # nada subido
