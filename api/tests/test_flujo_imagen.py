"""Flujo `.github/workflows/imagen.yml` (I-10; ADR 0030), revisado sin ejecutarlo.

- Solo se dispara a mano (workflow_dispatch).
- Toda acción está fijada por SHA de 40 caracteres.
- Permisos mínimos y ningún secreto propio (solo el GITHUB_TOKEN de la ejecución).
- Construye con el contexto adicional `panel-src` y publica en ghcr.io.
"""

import re
from pathlib import Path

FLUJO = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "imagen.yml"
TEXTO = FLUJO.read_text(encoding="utf-8")
SIN_COMENTARIOS = "\n".join(ln.split(" #", 1)[0] for ln in TEXTO.splitlines())


def test_solo_manual() -> None:
    bloque_on = re.search(r"^on:\n((?:  .*\n)+)", SIN_COMENTARIOS, re.MULTILINE).group(1)
    assert bloque_on.strip() == "workflow_dispatch:"


def test_acciones_fijadas_por_sha() -> None:
    usos = re.findall(r"uses:\s*(\S+)", SIN_COMENTARIOS)
    assert len(usos) == 5
    for uso in usos:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", uso), uso


def test_permisos_minimos_y_sin_secretos_propios() -> None:
    assert "permissions: {}" in SIN_COMENTARIOS
    assert set(re.findall(r"secrets\.(\w+)", SIN_COMENTARIOS)) == {"GITHUB_TOKEN"}
    assert "pull_request_target" not in SIN_COMENTARIOS
    assert "persist-credentials: false" in SIN_COMENTARIOS


def test_construye_con_panel_src_y_publica_en_ghcr() -> None:
    assert "panel-src=./panel" in SIN_COMENTARIOS
    assert "context: ./api" in SIN_COMENTARIOS
    assert "ghcr.io/" in SIN_COMENTARIOS
    assert "linux/amd64" in SIN_COMENTARIOS
