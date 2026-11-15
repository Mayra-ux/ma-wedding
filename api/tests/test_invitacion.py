"""Invitación conectada a la API (I-5): CSP, textos aprobados y reglas de seguridad (estático)."""

import importlib.util
import re
from pathlib import Path

import pytest

INDEX = Path(__file__).resolve().parents[2] / "invitacion" / "index.html"
HTML = INDEX.read_bytes().decode("utf-8")

_spec = importlib.util.spec_from_file_location(
    "csp_invitacion", Path(__file__).resolve().parents[1] / "tools" / "csp_invitacion.py"
)
csp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(csp)


def _modulo_rsvp() -> str:
    script = csp.scripts_en_linea(HTML)[0]
    inicio = script.index("// Confirmación de asistencia (I-5)")
    return script[inicio : script.index("// Mesa de regalos")]


def test_csp_coincide_con_el_script_y_con_api_base() -> None:
    assert csp.csp_actual(HTML) == csp.csp_esperada(HTML)
    assert f"connect-src {csp.origen_api(HTML)};" in csp.csp_actual(HTML)


def test_csp_solo_permite_lo_necesario() -> None:
    directivas = dict(d.strip().split(" ", 1) for d in csp.csp_actual(HTML).split(";"))
    assert directivas["default-src"] == "'none'"
    assert re.fullmatch(r"'sha256-[A-Za-z0-9+/]{43}='", directivas["script-src"])
    assert "'unsafe-inline'" not in directivas["script-src"]
    assert directivas["font-src"] == "https://fonts.gstatic.com"
    assert directivas["img-src"] == "'self' data:"
    assert directivas["base-uri"] == "'none'"


def test_el_hash_no_depende_de_crlf() -> None:
    cuerpo = csp.scripts_en_linea(HTML)[0]
    assert csp.hash_script(cuerpo) == csp.hash_script(cuerpo.replace("\n", "\r\n"))


def test_la_csp_va_antes_de_cualquier_recurso() -> None:
    i_csp = HTML.index('http-equiv="Content-Security-Policy"')
    assert i_csp < HTML.index("fonts.googleapis.com") and i_csp < HTML.index("<style")
    assert '<meta name="referrer" content="no-referrer">' in HTML


def test_un_solo_script_y_sin_manejadores_en_linea() -> None:
    assert len(re.findall(r"<script", HTML, re.I)) == 1
    assert not re.search(r"\son[a-z]+\s*=", HTML, re.I)
    assert "javascript:" not in HTML


@pytest.mark.parametrize(
    "texto",
    [
        "Vista previa del diseño",
        "[Nombre del invitado o familia]",
        "[fecha límite por definir]",
        ">2 lugares<",
        "2 de 2",
        "Confirma antes del",
    ],
)
def test_sin_placeholders_ni_leyendas_de_vista_previa(texto: str) -> None:
    assert texto not in HTML


APROBADOS = [
    "Abriendo tu invitación…",
    "Para confirmar tu asistencia, abre el enlace personal que te enviamos por WhatsApp. Si no lo "
    "encuentras, escríbenos a ese mismo chat y con gusto te lo reenviamos.",
    "Este enlace ya no está activo. Escríbenos al chat de WhatsApp donde recibiste tu invitación y "
    "te enviaremos uno nuevo.",
    "Ya registramos tu respuesta: ",
    ". Puedes modificarla hasta el ",
    "Ya registramos que no podrás acompañarnos. Si cambian tus planes, puedes "
    "modificarlo hasta el ",
    "El periodo de confirmación terminó el ",
    ". Si necesitas confirmar o hacer algún cambio, escríbenos al chat de WhatsApp donde recibiste "
    "tu invitación y lo revisamos con gusto.",
    "Tu respuesta quedó registrada: ",
    "no podrás acompañarnos",
    ". El periodo para modificarla terminó el ",
    "; si necesitas algún cambio, escríbenos al chat de WhatsApp.",
    "Gracias por ser parte de nuestra leyenda. La confirmación de asistencia ya está cerrada.",
    "No pudimos guardar tu respuesta. Revisa tu conexión e inténtalo de nuevo.",
    "Hiciste varios intentos seguidos. Espera unos minutos e inténtalo de nuevo.",
    "No pudimos abrir tu invitación. Revisa tu conexión e inténtalo de nuevo.",
    "REINTENTAR",
    "ENVIANDO…",
    "ALERGIAS O RESTRICCIONES ALIMENTICIAS (OPCIONAL)",
    'placeholder="Ej. vegetariano, alergia a nueces…"',
    "Solo la usaremos para preparar el banquete.",
    "Usaremos tus datos solo para organizar nuestra boda.",
    ">Aviso de privacidad</a>",
    "Confirma a más tardar el ",
    "¡Tu lugar en la leyenda está reservado!",
    "Gracias por avisarnos",
    "Te extrañaremos en este capítulo. Gracias por acompañarnos con tu cariño.",
    "Mayra [APELLIDOS] y Alejandro [APELLIDOS], novios.",
    "cualquier cambio a este aviso se publicará aquí mismo.",
]


@pytest.mark.parametrize("texto", APROBADOS)
def test_textos_aprobados_literales(texto: str) -> None:
    assert texto in HTML


def test_longitudes_maximas_en_los_campos() -> None:
    assert re.search(r'id="rsvp-alergias"[^>]*maxlength="200"', HTML)
    assert re.search(r'id="rsvp-msg"[^>]*maxlength="500"', HTML)


def test_el_modulo_rsvp_inserta_datos_solo_como_texto() -> None:
    modulo = _modulo_rsvp()
    assert "innerHTML" not in modulo and "insertAdjacentHTML" not in modulo
    assert "document.write" not in modulo and "eval(" not in modulo
    for campo in ("nombre_mostrar", "pases"):
        assert campo in modulo


def test_el_token_solo_va_en_el_cuerpo() -> None:
    modulo = _modulo_rsvp()
    assert "history.replaceState" in modulo and "sessionStorage" in modulo
    assert "credentials: 'omit'" in modulo and "referrerPolicy: 'no-referrer'" in modulo
    assert re.search(r"body: JSON\.stringify\(cuerpo\)", modulo)
    assert not re.search(r"['\"]\?token=|[?&]t=['\"]", modulo)
    assert "/api/v1/public/invitation/" in modulo


def test_vista_previa_de_whatsapp_sigue_generica() -> None:
    assert '<meta property="og:title" content="Mayra &amp; Alejandro · 06.03.2027">' in HTML
    assert '<meta property="og:image" content="/og.jpg">' in HTML
