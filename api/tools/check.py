"""Un solo comando para lint + formato + panel + tests: `uv run python tools/check.py`.

1. ruff (lint y formato) de la API.
2. Panel (I-9) DENTRO del contenedor node:24.22.3 fijado por digest (no hace falta Node en el
   equipo): copia el código a una carpeta del contenedor, `npm ci --ignore-scripts`,
   `npm audit signatures`, `npm audit`, pruebas (Vitest) y build; el build queda en panel/dist.
3. Levanta la DB descartable de pruebas (`db-test`, solo en 127.0.0.1).
4. pytest (exige panel/dist), con el nombre de cada prueba que falle (-rfE).

La salida completa de cada corrida queda en api/logs/check-AAAAMMDD-HHMMSS.log (ignorado por git).

Opciones:
  --e2e               además, la prueba de punta a punta del panel con Chrome o Edge (E2E=1)
  --capturas CARPETA  con --e2e, guarda las capturas de cada pantalla en 390 y 1440 px
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# Cada corrida guarda su salida completa aquí (ignorado por git: *.log).
LOGS = Path(__file__).resolve().parents[1] / "logs"
NODE_IMAGE = (
    "node:24.22.3-slim@sha256:dc26ae92c9fb15cf6b1d63e20f0944b2efe0f115b20e00be48fb23fceb061c54"
)
ARCHIVOS_PANEL = "package.json package-lock.json .npmrc index.html vite.config.js public src test"
SCRIPT_PANEL = (
    "set -e; mkdir /w; cd /panel; "
    f"cp -r {ARCHIVOS_PANEL} /w/; cd /w; "
    "npm ci --ignore-scripts --no-audit --no-fund; "
    "npm audit signatures; npm audit; "
    "npx vitest run; npm run build; "
    "rm -rf /panel/dist; cp -r dist /panel/dist"
)


def pasos(e2e: bool) -> list[tuple[str, list[str], Path | None]]:
    return [
        ("ruff check", [sys.executable, "-m", "ruff", "check", "."], None),
        ("ruff format --check", [sys.executable, "-m", "ruff", "format", "--check", "."], None),
        (
            "panel en el contenedor de Node (npm ci, audit, vitest, build)",
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{REPO / 'panel'}:/panel",
                "-v",
                "ma-panel-npm-cache:/root/.npm",
                NODE_IMAGE,
                "sh",
                "-c",
                SCRIPT_PANEL,
            ],
            REPO,
        ),
        (
            "db-test (docker compose --profile test up -d --wait db-test)",
            ["docker", "compose", "--profile", "test", "up", "-d", "--wait", "db-test"],  # noqa: S607
            REPO,
        ),
        # -rfE: el resumen nombra cada prueba que falle o dé error (I-10, prueba intermitente).
        ("pytest" + (" con E2E" if e2e else ""), [sys.executable, "-m", "pytest", "-rfE"], None),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e2e", action="store_true")
    parser.add_argument("--capturas")
    args = parser.parse_args()
    os.environ["PANEL_DIST_REQUERIDO"] = "1"
    if args.e2e:
        os.environ["E2E"] = "1"
    if args.capturas:
        os.environ["E2E_CAPTURAS"] = str(Path(args.capturas).resolve())
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    LOGS.mkdir(exist_ok=True)
    ruta_log = LOGS / f"check-{datetime.now():%Y%m%d-%H%M%S}.log"
    with ruta_log.open("wb") as log:

        def decir(texto: str) -> None:
            print(texto, flush=True)
            log.write((texto + "\n").encode("utf-8"))

        decir(f"check.py {' '.join(sys.argv[1:])} · log completo: {ruta_log}")
        for label, cmd, cwd in pasos(args.e2e):
            decir(f"\n== {label}")
            code = _correr(cmd, cwd, env, log)
            if code != 0:
                decir(f"\nFALLO: {label} (detalle en {ruta_log})")
                return code
        decir("\nOK: lint, formato, panel y tests" + (" (con E2E)" if args.e2e else ""))
    return 0


def _correr(cmd: list[str], cwd: Path | None, env: dict, log) -> int:  # noqa: ANN001
    """Ejecuta un paso mostrando su salida y guardándola completa en el log."""
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)  # noqa: S603
    for linea in proc.stdout:
        sys.stdout.buffer.write(linea)
        sys.stdout.flush()
        log.write(linea)
    return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
