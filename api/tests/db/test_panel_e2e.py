"""Prueba de punta a punta del panel (criterios de I-9; ADR 0015, 0026, 0027, 0028, 0029).

Un uvicorn real sirve la API y el build del panel (panel/dist) con la DB de pruebas, llaves
y reloj simulados y el Google simulado. El navegador es el Chrome o el Edge instalado
(Playwright para Python, sin descargar navegadores). Todo es ficticio: correos
@ejemplo.invalid y teléfonos de la serie 555-01XX.

- El inicio de sesión con Google se intercepta en el navegador: la petición a
  accounts.google.com regresa al callback con un código que el Google simulado canjea.
- wa.me también se intercepta: se comprueba la URL que abriría WhatsApp, sin abrirlo.
- En todo el recorrido: cero violaciones de CSP (incluido Trusted Types), cero errores de
  JavaScript y ninguna respuesta de error inesperada.

Solo corre con E2E=1 (`uv run python tools/check.py --e2e`). Con E2E_CAPTURAS=<carpeta>
guarda además las capturas de cada pantalla en 390 y 1440 px.
"""

import io
import json
import os
import secrets
import socket
import threading
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("E2E"), reason="solo con E2E=1 (check --e2e)")
sync_api = pytest.importorskip("playwright.sync_api")

import openpyxl  # noqa: E402
import uvicorn  # noqa: E402

from app.config import Settings  # noqa: E402
from app.db import make_sessionmaker  # noqa: E402
from app.estado import MX  # noqa: E402
from app.main import create_app  # noqa: E402
from app.sesiones_panel import generar_secreto_sesion  # noqa: E402
from tests.db.test_auth_panel import NOVIA, PLANNER  # noqa: E402
from tests.db.util import llaves_de_prueba  # noqa: E402
from tests.google_simulado import CLIENT_ID, GoogleSimulado  # noqa: E402
from tests.planilla_ficticia import HOJA_NOVIA, HOJA_NOVIO, fila, libro  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
DIST = REPO / "panel" / "dist"
CALLBACK = "/api/v1/auth/google/callback"
TEL1, TEL2 = "2025550123", "2025550199"  # serie 555-01XX, reservada para ficción
MX52 = "+" + "52"  # se arma por partes (tests/test_sin_telefonos_reales.py)
NOVIEMBRE = datetime(2026, 11, 20, 12, 0, tzinfo=MX)
FEBRERO = datetime(2027, 2, 1, 12, 0, tzinfo=MX)
CIERRE_PLANNER = datetime(2027, 3, 7, 0, 0, tzinfo=MX)
CAPTURAS = os.environ.get("E2E_CAPTURAS")
VIOLACIONES_JS = """
document.addEventListener('securitypolicyviolation', (e) =>
  window.__reportarCSP(e.violatedDirective + ' ' + (e.blockedURI || '') + ' ' + (e.sample || '')))
"""


# --------------------------------------------------------------------------- servidor y navegador
def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Servidor:
    def __init__(self, engine, reloj) -> None:  # noqa: ANN001
        self.reloj = reloj
        self.google = GoogleSimulado()
        self.puerto = _puerto_libre()
        self.base = f"http://localhost:{self.puerto}"
        settings = Settings(
            panel_origin=self.base,
            google_client_id=CLIENT_ID,
            google_client_secret="secreto-ficticio-de-prueba",  # noqa: S106
            session_secret=generar_secreto_sesion(),
            admin_emails_novios=NOVIA,
            admin_emails_planner=PLANNER,
            panel_dir=DIST,
            rate_limit_ip_per_hour=100_000,
        )
        app = create_app(
            settings,
            sesiones=make_sessionmaker(engine),
            llaves=llaves_de_prueba(),
            reloj=reloj,
            google=self.google,
        )
        config = uvicorn.Config(app, host="127.0.0.1", port=self.puerto, log_level="warning")
        self.server = uvicorn.Server(config)
        self.hilo = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> "Servidor":
        self.hilo.start()
        for _ in range(200):
            if self.server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("uvicorn no arrancó")

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self.server.should_exit = True
        self.hilo.join(10)


@pytest.fixture
def servidor(app_engine, reloj, limpiar):  # noqa: ANN001, ANN201
    if not (DIST / "index.html").is_file():
        pytest.fail("panel/dist no existe: compílalo con tools/check.py")
    reloj.ahora = NOVIEMBRE
    with Servidor(app_engine, reloj) as s:
        yield s


@pytest.fixture(scope="module")
def navegador():  # noqa: ANN201
    with sync_api.sync_playwright() as p:
        ultimo = None
        for canal in ("chrome", "msedge"):
            try:
                b = p.chromium.launch(channel=canal, headless=True)
                break
            except Exception as exc:  # noqa: BLE001
                ultimo = exc
        else:
            pytest.fail(f"No se encontró Chrome ni Edge instalados: {type(ultimo).__name__}")
        yield b
        b.close()


class Vigia:
    """Registra violaciones de CSP, errores de JavaScript y respuestas de error."""

    def __init__(self) -> None:
        self.csp: list[str] = []
        self.js: list[str] = []
        self.respuestas: list[tuple[int, str]] = []
        self.permitidas: set[tuple[int, str]] = set()

    def revisar(self) -> None:
        inesperadas = [(s, r) for s, r in self.respuestas if (s, r) not in self.permitidas]
        assert self.csp == [], self.csp
        assert self.js == [], self.js
        assert inesperadas == [], inesperadas


class Navegacion:
    """Un rol en su propio contexto del navegador (cookies aparte)."""

    def __init__(self, navegador, servidor: Servidor, ancho: int = 390, alto: int = 844) -> None:  # noqa: ANN001
        self.s = servidor
        self.correo = None
        self.vigia = Vigia()
        self.ctx = navegador.new_context(
            viewport={"width": ancho, "height": alto},
            locale="es-MX",
            timezone_id="America/Mexico_City",
            accept_downloads=True,
        )
        self.ctx.expose_function("__reportarCSP", lambda v: self.vigia.csp.append(v))
        self.ctx.add_init_script(VIOLACIONES_JS)
        # La redirección a Google se reemplaza en la respuesta del login (el navegador nunca
        # llega a Google); cualquier petición a Google que se escape se aborta.
        self.ctx.route(servidor.base + "/api/v1/auth/google/login", self._login)
        self.ctx.route("https://accounts.google.com/**", lambda r: r.abort())
        self.ctx.route(
            "https://wa.me/**", lambda r: r.fulfill(status=200, body="WhatsApp simulado")
        )
        self.page = self.ctx.new_page()
        self.page.on("pageerror", lambda e: self.vigia.js.append(str(e)))
        self.page.on(
            "console",
            lambda m: (
                m.type == "error"
                and not m.text.startswith("Failed to load resource")  # se revisan como respuestas
                and self.vigia.js.append(m.text)
            ),
        )
        self.page.on("response", self._respuesta)
        self.vigia.permitidas.add((401, "/api/v1/auth/me"))  # antes de iniciar sesión

    def _respuesta(self, r) -> None:  # noqa: ANN001
        ruta = urllib.parse.urlsplit(r.url).path
        if r.status >= 400 and r.url.startswith(self.s.base):
            self.vigia.respuestas.append((r.status, ruta))

    def _login(self, route) -> None:  # noqa: ANN001
        r = route.fetch(max_redirects=0)
        assert r.status == 302
        google = r.headers["location"]
        assert google.startswith("https://accounts.google.com/")
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(google).query))
        codigo = "codigo-e2e-" + secrets.token_hex(6)
        self.s.google.preparar(codigo, self.correo, q["nonce"])
        destino = f"{self.s.base}{CALLBACK}?code={codigo}&state={urllib.parse.quote(q['state'])}"
        route.fulfill(response=r, headers={**r.headers, "location": destino})

    # --- acciones
    def entrar(self, correo: str) -> None:
        self.correo = correo
        self.page.goto(self.s.base + "/admin/")
        self.page.get_by_role("link", name="Entrar con Google").click()
        self.titulo("Invitaciones")

    def titulo(self, texto: str) -> None:
        sync_api.expect(self.page.get_by_role("heading", level=1)).to_have_text(texto)

    def boton(self, nombre: str):  # noqa: ANN201
        return self.page.get_by_role("button", name=nombre, exact=True)

    def ir(self, hash_: str) -> None:
        self.page.evaluate("h => { window.location.hash = h }", hash_)

    def api(self, metodo: str, ruta: str, datos: dict | None = None):  # noqa: ANN201
        """Llamada directa a la API con la sesión del navegador (para preparar datos)."""
        me = self.page.request.get(self.s.base + "/api/v1/auth/me").json()
        r = self.page.request.fetch(
            self.s.base + "/api/v1/admin" + ruta,
            method=metodo,
            data=json.dumps(datos) if datos is not None else None,
            headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": me["csrf_token"],
                "Origin": self.s.base,
            },
        )
        assert r.ok, (r.status, r.text())
        return r.json() if r.status != 204 else None

    def ok(self, texto: str) -> None:
        sync_api.expect(self.page.locator(".ok").last).to_contain_text(texto)

    def cerrar(self) -> None:
        self.vigia.revisar()
        self.ctx.close()


def mover_reloj(s: Servidor, instante: datetime, *navs: Navegacion) -> None:
    """Un salto de horas vence la sesión por inactividad (8 h): cada rol vuelve a entrar y la
    pantalla muestra «Tu sesión terminó»."""
    s.reloj.ahora = instante
    for n in navs:
        n.vigia.permitidas.add((401, "/api/v1/auth/me"))
        n.page.reload()
        n.page.get_by_role("link", name="Entrar con Google").click()
        n.titulo("Invitaciones")


def texto_whatsapp(page) -> str:  # noqa: ANN001
    return page.get_by_test_id("texto-whatsapp").inner_text()


def archivo_ficticio() -> bytes:
    """Dos hojas de invitados (obliga a elegir hoja) con datos ficticios."""
    novio = [
        fila(no_planner=1.0, nombre_mostrar="Familia Importada Uno", pases=2.0, adultos=2.0,
             telefono_principal=float("2025550101")),
        fila(no_planner=2.0, nombre_mostrar="Familia Importada Dos", pases=3.0, adultos=2.0,
             ninos_autorizados=1.0, telefono_principal="202 555 0102"),
    ]  # fmt: skip
    novia = [fila(no_planner=1.0, nombre_mostrar="Familia de la Novia", pases=1.0, adultos=1.0)]
    return libro(novio, novia)


# =========================================================================== flujos de los novios
def test_flujo_completo_de_los_novios(servidor: Servidor, navegador) -> None:  # noqa: ANN001, PLR0915
    n = Navegacion(navegador, servidor)
    page = n.page
    n.ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=servidor.base)
    n.entrar(NOVIA)
    sync_api.expect(page.locator(".rol-usuario")).to_have_text("Novios")

    # --- crear
    page.get_by_role("link", name="Nueva invitación").click()
    n.titulo("Nueva invitación")
    page.get_by_label("Nombre a mostrar").fill("Familia Ficticia E2E")
    page.get_by_label("Adultos").fill("2")
    page.get_by_label("Niños autorizados").fill("1")
    page.get_by_label("Invitado de").select_option("Novia")
    page.get_by_label("Grupo").select_option("Familia")
    page.get_by_label("Paje").check()
    page.get_by_label("Teléfono principal").fill(TEL1)
    page.locator("#contacto_alterno_nombre").fill("Contacto Ficticio")
    page.get_by_label("Teléfono del contacto alterno").fill(TEL2)
    sync_api.expect(page.locator(".pases strong")).to_have_text("3")
    n.boton("Crear invitación").click()
    n.titulo("Familia Ficticia E2E")
    sync_api.expect(page.locator(".titulo-pantalla .sub")).to_have_text("INV-001")

    # --- enlace: generar, ver y copiar
    n.boton("Generar enlace").click()
    n.ok("Enlace generado.")
    url = page.get_by_label("Enlace de la invitación").input_value()
    assert url.startswith("http://localhost:8080/#t=")
    n.boton("Copiar").click()
    n.ok("Enlace copiado.")
    assert page.evaluate("navigator.clipboard.readText()") == url

    # --- WhatsApp con enlace: principal y alterno (texto a aprobado) y marca de enviado
    n.boton("WhatsApp al principal").click()
    esperado = (
        "Hola, Familia Ficticia E2E: con mucha ilusión te invitamos a nuestra boda el sábado 6 "
        "de marzo de 2027. Es peligroso ir solo… ¡acompáñanos! Aquí está tu invitación, donde "
        "puedes confirmar tu asistencia a más tardar el sábado 30 de enero de 2027:\n"
        f"{url}\nCon cariño, Mayra y Alejandro"
    )
    assert texto_whatsapp(page) == esperado
    abrir = page.get_by_role("link", name="Abrir en WhatsApp")
    href = abrir.get_attribute("href")
    assert href.startswith(f"https://wa.me/52{TEL1}?text=")
    assert urllib.parse.unquote(href.split("text=")[1]) == esperado
    assert abrir.get_attribute("rel") == "noopener noreferrer"
    with n.ctx.expect_page() as nueva:
        abrir.click()
    assert nueva.value.url == href
    nueva.value.close()
    n.boton("Marcar enlace como enviado").click()
    n.ok("Enlace marcado como enviado por WhatsApp.")
    sync_api.expect(page.locator("#t-enlace + dl")).to_contain_text("por WhatsApp")
    n.boton("WhatsApp al alterno").click()
    href_alterno = page.get_by_role("link", name="Abrir en WhatsApp").get_attribute("href")
    assert href_alterno.startswith(f"https://wa.me/52{TEL2}?text=")
    n.boton("Cerrar").click()

    # --- recordatorio para confirmar (sin enlace) y su marca
    n.boton("Recordatorio al principal").click()
    recordatorio = texto_whatsapp(page)
    assert recordatorio.startswith("Hola, te recordamos confirmar tu asistencia")
    assert "a más tardar el sábado 30 de enero de 2027" in recordatorio
    assert "#t=" not in recordatorio and url not in recordatorio
    n.boton("Marcar recordatorio como enviado").click()
    n.ok("Recordatorio marcado como enviado.")
    sync_api.expect(page.locator("#t-recordatorios ~ p.tenue")).to_contain_text(
        "1 enviado; el último para confirmar"
    )

    # --- registrar respuesta (texto de usuario como texto)
    n.boton("Registrar respuesta").click()
    page.get_by_label("Lugares confirmados (1 a 3)").fill("3")
    page.get_by_label("Mensaje").fill("<b>¡Felicidades!</b>")
    n.boton("Guardar respuesta").click()
    n.ok("Respuesta registrada.")
    sync_api.expect(page.locator(".mensaje-invitado").first).to_have_text("<b>¡Felicidades!</b>")
    assert page.locator(".detalle b").count() == 0

    # --- desbloqueo: deshabilitado antes del plazo; posible el 1 feb
    sync_api.expect(page.locator("#t-desbloqueo ~ .nota")).to_contain_text("El plazo sigue abierto")
    codigo = "INV-001"
    mover_reloj(servidor, FEBRERO, n)
    n.ir(f"#/inv/{codigo}")
    n.titulo("Familia Ficticia E2E")
    page.get_by_label("Desbloquear hasta").fill("2027-02-03")
    n.boton("Desbloquear").click()
    n.ok("Invitación desbloqueada hasta el final del miércoles, 3 de febrero de 2027.")
    sync_api.expect(page.locator("#t-desbloqueo")).to_be_visible()
    assert page.get_by_role("button", name="Retirar desbloqueo").is_visible()
    n.boton("Recordatorio al principal").click()
    assert texto_whatsapp(page).startswith("Hola, te recordamos que la boda de Mayra y Alejandro")
    n.boton("Cerrar").click()

    # --- archivar (diálogo) → sale de la lista y del enlace; restaurar
    n.boton("Archivar").click()
    dialogo = page.get_by_role("dialog")
    sync_api.expect(dialogo).to_contain_text("su enlace deja de funcionar")
    dialogo.get_by_role("button", name="Archivar").click()
    n.ok("Invitación archivada. Su enlace quedó revocado.")
    sync_api.expect(page.locator("#t-enlace")).to_have_count(0)
    n.ir("#/")
    n.titulo("Invitaciones")
    sync_api.expect(page.locator(".conteo")).to_have_text("0 invitaciones")
    page.locator("summary", has_text="Filtros").click()
    page.get_by_label("Mostrar archivadas").check()
    sync_api.expect(page.locator(".tarjeta-archivada")).to_have_count(1)

    # --- importar: elegir hoja y lado, vista previa, aplicar
    n.ir("#/importar")
    n.titulo("Importar lista")
    page.get_by_label("Archivo").set_input_files(
        files=[
            {
                "name": "lista-ficticia.xlsx",
                "mimeType": "application/octet-stream",
                "buffer": archivo_ficticio(),
            }
        ]
    )
    page.get_by_label("Lado por defecto").select_option("Novio")
    n.vigia.permitidas.add((422, "/api/v1/admin/imports/preview"))  # hoja_requerida
    n.boton("Ver vista previa").click()
    sync_api.expect(page.locator(".error")).to_contain_text("Elige cuál importar")
    page.get_by_label(HOJA_NOVIO, exact=True).check()
    n.boton("Ver vista previa").click()
    sync_api.expect(
        page.get_by_role("heading", name=f"Vista previa · {HOJA_NOVIO}")
    ).to_be_visible()
    sync_api.expect(page.locator(".tarjeta")).to_have_count(2)
    assert page.get_by_label(HOJA_NOVIA, exact=True).is_visible()
    n.boton("Aplicar importación").click()
    n.ok("2 nuevas, 0 actualizadas y 0 sin cambios.")

    # --- confirmar una importada (para «solo confirmados») y exportar
    n.api("PUT", "/invitations/INV-002/response", {"asiste": True, "confirmados": 2})
    n.ir("#/exportar")
    n.titulo("Exportar lista")
    page.get_by_label("Solo confirmados").check()
    with page.expect_download() as descarga:
        n.boton("Descargar").click()
    d = descarga.value
    assert d.suggested_filename == "invitados-confirmados-2027-02-01.xlsx"
    ws = openpyxl.load_workbook(io.BytesIO(Path(d.path()).read_bytes())).active
    filas = list(ws.iter_rows(values_only=True))
    assert len(filas[0]) == 19 and filas[0][0] == "Código INV"
    assert [f[0] for f in filas[1:]] == ["INV-002"]  # INV-001 archivada, INV-003 pendiente
    assert all("#t=" not in str(c) for f in filas for c in f)

    # --- totales del navegador = resumen del servidor
    n.ir("#/")
    n.titulo("Invitaciones")
    servidor_resumen = page.request.get(servidor.base + "/api/v1/admin/summary").json()
    for testid, clave in (
        ("resumen-invitaciones", "invitaciones"),
        ("resumen-pases", "pases_asignados"),
        ("resumen-confirmados", "personas_confirmadas"),
        ("resumen-ninos", "ninos_autorizados"),
        ("resumen-infantes", "infantes"),
    ):
        sync_api.expect(page.get_by_test_id(testid).locator("dd")).to_have_text(
            str(servidor_resumen[clave])
        )
    pendientes = servidor_resumen["por_estado"]["pendiente"]["invitaciones"]
    sync_api.expect(page.get_by_test_id("resumen-pendientes").locator("dd")).to_have_text(
        str(pendientes)
    )

    # --- búsqueda y filtros en el navegador
    page.get_by_label("Buscar por nombre, código o No.").fill("importada dos")
    sync_api.expect(page.locator(".tarjeta")).to_have_count(1)
    sync_api.expect(page.locator(".conteo")).to_contain_text("Mostrando 1 de 3")

    # --- actividad y cierre de sesión
    n.ir("#/actividad")
    n.titulo("Actividad")
    sync_api.expect(page.locator(".actividad")).to_contain_text("Importó un archivo")
    sync_api.expect(page.locator(".actividad")).to_contain_text("Marcó el enlace como enviado")
    n.boton("Cerrar sesión").click()
    sync_api.expect(page.locator(".login-motivo")).to_have_text("Cerraste sesión.")
    n.cerrar()


def test_teclado_crear_y_abrir_detalle(servidor: Servidor, navegador) -> None:  # noqa: ANN001
    """Crear una invitación y abrir su detalle solo con el teclado; el foco siempre visible."""
    n = Navegacion(navegador, servidor, 1440, 900)
    page = n.page
    n.entrar(NOVIA)

    def tab_hasta(condicion: str, maximo: int = 40) -> None:
        for _ in range(maximo):
            page.keyboard.press("Tab")
            if page.evaluate(
                f"(() => {{ const e = document.activeElement; return {condicion} }})()"
            ):
                estilo = page.evaluate(
                    "(() => { const s = getComputedStyle(document.activeElement);"
                    " return s.outlineStyle + ' ' + s.outlineWidth })()"
                )
                assert estilo.startswith("solid") and estilo != "solid 0px", estilo
                return
        raise AssertionError(f"el foco no llegó a: {condicion}")

    # Al entrar, el foco queda en el título de la pantalla (lectores de pantalla).
    assert (
        page.evaluate("document.activeElement.tagName + ' ' + document.activeElement.textContent")
        == "H1 Invitaciones"
    )
    # «Saltar al contenido» es el primer elemento enfocable y lleva el foco al contenido.
    primero = page.evaluate(
        "document.querySelector('a[href], button, input, select, textarea, "
        '[tabindex]:not([tabindex="-1"])\').textContent'
    )
    assert primero == "Saltar al contenido"
    page.locator(".saltar").focus()
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.id") == "contenido"
    tab_hasta("e.textContent === 'Nueva invitación'")
    page.keyboard.press("Enter")
    n.titulo("Nueva invitación")
    tab_hasta("e.id === 'nombre_mostrar'")
    page.keyboard.type("Familia Teclado")
    tab_hasta("e.id === 'adultos'")
    page.keyboard.press("Control+A")
    page.keyboard.type("2")
    tab_hasta("e.id === 'rol-10'")  # Paje
    page.keyboard.press("Space")
    tab_hasta("e.type === 'submit'")
    page.keyboard.press("Enter")
    n.titulo("Familia Teclado")
    tab_hasta("e.textContent === 'Archivar'")
    page.keyboard.press("Enter")
    sync_api.expect(page.get_by_role("dialog")).to_be_visible()
    page.keyboard.press("Escape")
    sync_api.expect(page.get_by_role("dialog")).to_be_hidden()
    assert page.evaluate("document.activeElement.textContent") == "Archivar"  # foco devuelto
    page.keyboard.press("Shift+Tab")  # de vuelta hacia arriba, hasta «← Invitaciones»
    for _ in range(10):
        if page.evaluate("document.activeElement.textContent") == "← Invitaciones":
            break
        page.keyboard.press("Shift+Tab")
    page.keyboard.press("Enter")
    n.titulo("Invitaciones")
    tab_hasta("e.textContent === 'Familia Teclado'")
    page.keyboard.press("Enter")
    n.titulo("Familia Teclado")
    n.cerrar()


# =========================================================================== planner
def test_planner_ve_todo_salvo_enlaces_y_solo_marca_recordatorios(
    servidor: Servidor, navegador
) -> None:  # noqa: ANN001
    novios = Navegacion(navegador, servidor)
    novios.entrar(NOVIA)
    codigo = novios.api("POST", "/invitations", {
        "nombre_mostrar": "Familia Ficticia", "adultos": 2, "telefono_principal": TEL1,
    })["codigo"]  # fmt: skip
    novios.api("POST", f"/invitations/{codigo}/link")
    novios.api(
        "PUT",
        f"/invitations/{codigo}/response",
        {"asiste": True, "confirmados": 2, "mensaje": "¡Nos vemos!"},
    )
    novios.cerrar()

    n = Navegacion(navegador, servidor)
    page = n.page
    n.entrar(PLANNER)
    sync_api.expect(page.locator(".rol-usuario")).to_have_text("Planner")
    menu = page.get_by_role("navigation", name="Secciones")
    sync_api.expect(menu.get_by_role("link")).to_have_text(
        ["Invitaciones", "Exportar", "Actividad"]
    )
    assert page.get_by_role("link", name="Nueva invitación").count() == 0

    page.get_by_role("link", name="Familia Ficticia").click()
    n.titulo("Familia Ficticia")
    titulos = page.locator("h2").all_inner_texts()
    assert titulos == ["Datos", "Respuesta", "Recordatorios", "Historial de respuestas"]
    sync_api.expect(page.locator(".detalle")).to_contain_text("¡Nos vemos!")
    botones = [
        b.strip() for b in page.locator(".detalle button, .detalle a.boton").all_inner_texts()
    ]
    assert botones == ["Recordatorio al principal"]
    assert "#t=" not in page.content()

    n.boton("Recordatorio al principal").click()
    assert "#t=" not in texto_whatsapp(page)
    n.boton("Marcar recordatorio como enviado").click()
    n.ok("Recordatorio marcado como enviado.")

    n.ir("#/actividad")
    n.titulo("Actividad")
    sync_api.expect(page.locator(".actividad")).to_contain_text(
        "Marcó un recordatorio como enviado"
    )
    n.ir("#/importar")
    n.titulo("Sin permiso")
    n.ir(f"#/inv/{codigo}/editar")
    n.titulo("Sin permiso")

    n.ir("#/exportar")
    n.titulo("Exportar lista")
    with page.expect_download() as descarga:
        n.boton("Descargar").click()
    ws = openpyxl.load_workbook(io.BytesIO(Path(descarga.value.path()).read_bytes())).active
    assert len(next(ws.iter_rows(values_only=True))) == 19

    # Desde el 7 mar 00:00 la planner queda en solo lectura (ADR 0027).
    mover_reloj(servidor, CIERRE_PLANNER, n)
    n.ir(f"#/inv/{codigo}")
    n.titulo("Familia Ficticia")
    sync_api.expect(page.locator("#t-recordatorios + p")).to_have_text(
        "El periodo de recordatorios terminó."
    )
    assert page.locator(".detalle button").count() == 0
    n.cerrar()


def test_cierre_por_inactividad_en_el_navegador(servidor: Servidor, navegador) -> None:  # noqa: ANN001
    """A los 30 min sin interacción el panel cierra la sesión (también en el servidor)."""
    n = Navegacion(navegador, servidor)
    page = n.page
    page.clock.install()
    n.entrar(NOVIA)
    page.clock.run_for(29 * 60 * 1000)
    sync_api.expect(page.get_by_role("heading", level=1)).to_have_text("Invitaciones")
    page.clock.run_for(2 * 60 * 1000)
    sync_api.expect(page.locator(".login-motivo")).to_contain_text("30 minutos sin actividad")
    me = page.request.get(servidor.base + "/api/v1/auth/me")
    assert me.status == 401  # la sesión ya no existe en el servidor
    n.cerrar()


# =========================================================================== capturas
@pytest.mark.skipif(not CAPTURAS, reason="solo con E2E_CAPTURAS=<carpeta>")
@pytest.mark.parametrize("ancho", [390, 1440])
def test_capturas(servidor: Servidor, navegador, ancho: int) -> None:  # noqa: ANN001, PLR0915
    destino = Path(CAPTURAS)
    destino.mkdir(parents=True, exist_ok=True)
    n = Navegacion(navegador, servidor, ancho, 844 if ancho == 390 else 900)
    page = n.page

    def foto(nombre: str) -> None:
        page.wait_for_timeout(150)
        page.screenshot(path=str(destino / f"{nombre}-{ancho}.png"), full_page=True)

    page.goto(servidor.base + "/admin/")
    page.get_by_role("link", name="Entrar con Google").wait_for()
    foto("01-inicio-de-sesion")
    n.entrar(NOVIA)
    datos = [
        ("Familia Ficticia Uno", 2, 1, 1, "Novia", "Familia", ["Padrinos de lazo"], TEL1, True),
        ("Familia Ficticia Dos", 3, 0, 0, "Novio", "Amigos", [], "2025550102", True),
        ("Persona Ficticia + acompañante", 2, 0, 0, "Novio", "Trabajo", [], "2025550103", False),
        ("Familia Ficticia Cuatro", 4, 2, 0, "Ambos", "Familia", ["Paje"], None, False),
        ("Amigos Ficticios", 1, 0, 0, None, "Otro", [], "2025550105", False),
    ]
    for nombre, ad, ni, inf, lado, grupo, roles, tel, enlace in datos:
        c = n.api("POST", "/invitations", {
            "nombre_mostrar": nombre, "adultos": ad, "ninos_autorizados": ni, "infantes": inf,
            "lado": lado, "grupo": grupo, "roles": roles, "telefono_principal": tel,
            "contacto_alterno_nombre": "Contacto Ficticio" if tel == TEL1 else None,
            "contacto_alterno_tel": TEL2 if tel == TEL1 else None,
            "nota_interna": "Mesa cerca de la pista" if tel == TEL1 else None,
        })["codigo"]  # fmt: skip
        if enlace:
            n.api("POST", f"/invitations/{c}/link")
            n.api("POST", f"/invitations/{c}/link/sent", {"origen": "whatsapp"})
    n.api(
        "PUT",
        "/invitations/INV-001/response",
        {
            "asiste": True,
            "confirmados": 3,
            "alergias": "Nueces",
            "mensaje": "¡Muchas felicidades! Ahí estaremos.",
        },
    )
    n.api(
        "PUT",
        "/invitations/INV-002/response",
        {"asiste": False, "confirmados": 0, "mensaje": "Lo sentimos mucho."},
    )
    n.api("POST", "/invitations/INV-001/reminder/sent", {"destino": "principal"})
    n.api("POST", "/invitations/INV-005/archive")

    n.ir("#/")
    page.reload()
    n.titulo("Invitaciones")
    foto("02-lista")
    if ancho == 390:
        page.locator("summary", has_text="Filtros").click()
    page.get_by_label("Estado").select_option("pendiente")
    page.get_by_text("Ver por estado, lado, grupo y rol").click()
    foto("03-lista-filtros-y-desglose")

    n.ir("#/inv/INV-001")
    n.titulo("Familia Ficticia Uno")
    foto("04-detalle-novios")
    n.boton("WhatsApp al principal").click()
    page.get_by_test_id("texto-whatsapp").wait_for()
    foto("05-detalle-whatsapp-con-enlace")
    n.boton("Cerrar").click()
    n.boton("Ver enlace").click()
    n.boton("Recordatorio al principal").click()
    page.get_by_test_id("texto-whatsapp").wait_for()
    foto("06-detalle-enlace-y-recordatorio")
    n.boton("Cerrar").click()
    n.boton("Registrar respuesta").click()
    foto("07-detalle-registrar-respuesta")
    n.boton("Archivar").click()
    page.get_by_role("dialog").wait_for()
    foto("08-dialogo-archivar")
    page.keyboard.press("Escape")

    n.ir("#/nueva")
    n.titulo("Nueva invitación")
    n.boton("Crear invitación").click()  # sin nombre: muestra los errores
    page.locator(".error-campo").first.wait_for()
    foto("09-crear-con-errores")
    n.ir("#/inv/INV-001/editar")
    n.titulo("Editar invitación")
    foto("10-editar")

    n.ir("#/importar")
    n.titulo("Importar lista")
    page.get_by_label("Archivo").set_input_files(
        files=[
            {
                "name": "lista-ficticia.xlsx",
                "mimeType": "application/octet-stream",
                "buffer": libro(
                    [
                        fila(
                            no_planner=1.0,
                            nombre_mostrar="Familia Ficticia Uno",
                            pases=3.0,
                            adultos=2.0,
                        ),
                        fila(
                            no_planner=2.0,
                            nombre_mostrar="Persona Ficticia + acompañante",
                            pases=3.0,
                            adultos=2.0,
                        ),
                        fila(
                            no_planner=3.0,
                            nombre_mostrar="Familia Nueva",
                            pases=2.0,
                            adultos=2.0,
                            telefono_principal="202 555 0106",
                        ),
                        fila(no_planner=4.0, nombre_mostrar="Fila Sin Adultos", pases=2.0),
                    ]
                ),
            }
        ]  # fmt: skip
    )
    page.get_by_label("Lado por defecto").select_option("Novio")
    n.boton("Ver vista previa").click()
    page.get_by_role("heading", name="Vista previa · Lista de invitados").wait_for()
    foto("11-importar-vista-previa")

    n.ir("#/exportar")
    n.titulo("Exportar lista")
    foto("12-exportar")
    n.ir("#/actividad")
    n.titulo("Actividad")
    foto("13-actividad")

    mover_reloj(servidor, FEBRERO, n)
    n.ir("#/inv/INV-003")
    n.titulo("Persona Ficticia + acompañante")
    page.locator("#t-desbloqueo").scroll_into_view_if_needed()
    foto("14-detalle-desbloqueo-febrero")
    n.vigia.permitidas.add((422, "/api/v1/admin/imports/preview"))
    n.cerrar()

    p = Navegacion(navegador, servidor, ancho, 844 if ancho == 390 else 900)
    p.entrar(PLANNER)
    p.ir("#/inv/INV-001")
    p.titulo("Familia Ficticia Uno")
    p.page.wait_for_timeout(150)
    p.page.screenshot(path=str(destino / f"15-detalle-planner-{ancho}.png"), full_page=True)
    p.cerrar()
