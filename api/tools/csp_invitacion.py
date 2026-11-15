"""CSP de la invitación (I-5, doc 08 §8.3 bis).

La URL de la API se edita en UN solo lugar: `<meta name="api-base">` de invitacion/index.html.
Este script recalcula la CSP a partir de ella y del script en línea:

    uv run python tools/csp_invitacion.py --actualizar   # reescribe la meta CSP
    uv run python tools/csp_invitacion.py                # solo verifica (sale con 1 si no coincide)

El hash se calcula con saltos de línea LF porque el navegador normaliza CRLF → LF antes de
calcularlo; así sirve igual para la copia local (CRLF en Windows) y la publicada (LF).
"""

import base64
import hashlib
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

INDEX = Path(__file__).resolve().parents[2] / "invitacion" / "index.html"

_SCRIPT = re.compile(r"<script(?P<attrs>[^>]*)>(?P<cuerpo>.*?)</script>", re.S | re.I)
_API = re.compile(r'<meta name="api-base" content="([^"]*)">')
_CSP = re.compile(r'(<meta http-equiv="Content-Security-Policy" content=")([^"]*)(">)')


def _lf(texto: str) -> str:
    return texto.replace("\r\n", "\n").replace("\r", "\n")


def scripts_en_linea(html: str) -> list[str]:
    return [
        m.group("cuerpo") for m in _SCRIPT.finditer(_lf(html)) if "src=" not in m.group("attrs")
    ]


def hash_script(cuerpo: str) -> str:
    return base64.b64encode(hashlib.sha256(_lf(cuerpo).encode("utf-8")).digest()).decode()


def origen_api(html: str) -> str:
    m = _API.search(html)
    if not m:
        raise ValueError('falta <meta name="api-base">')
    p = urlsplit(m.group(1))
    if p.scheme not in {"http", "https"} or not p.netloc or p.path not in {"", "/"} or p.query:
        raise ValueError("api-base debe ser solo esquema y host, p. ej. https://api.ejemplo.mx")
    return f"{p.scheme}://{p.netloc}"


def csp_esperada(html: str) -> str:
    scripts = scripts_en_linea(html)
    if len(scripts) != 1:
        raise ValueError(f"se esperaba 1 script en línea y hay {len(scripts)}")
    return "; ".join(
        [
            "default-src 'none'",
            f"script-src 'sha256-{hash_script(scripts[0])}'",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src https://fonts.gstatic.com",
            "img-src 'self' data:",
            f"connect-src {origen_api(html)}",
            "base-uri 'none'",
            "form-action 'none'",
        ]
    )


def csp_actual(html: str) -> str:
    m = _CSP.search(html)
    if not m:
        raise ValueError("falta la meta Content-Security-Policy")
    return m.group(2)


def main(argv: list[str]) -> int:
    datos = INDEX.read_bytes()
    html = datos.decode("utf-8")
    esperada = csp_esperada(html)
    if "--actualizar" in argv:
        nuevo = _CSP.sub(lambda m: m.group(1) + esperada + m.group(3), html, count=1)
        INDEX.write_bytes(nuevo.encode("utf-8"))  # conserva los fines de línea del archivo
        print(f"CSP actualizada en {INDEX.name}: connect-src {origen_api(html)}")
        return 0
    if csp_actual(html) != esperada:
        print(
            "La CSP no coincide con el script o con api-base. Corre: "
            "uv run python tools/csp_invitacion.py --actualizar"
        )
        return 1
    print("CSP de la invitación: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
