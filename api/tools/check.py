"""Un solo comando para lint + formato + tests: `uv run python tools/check.py`.

Levanta antes la DB descartable de pruebas (`db-test`, solo en 127.0.0.1).
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

STEPS = [
    ("ruff check", [sys.executable, "-m", "ruff", "check", "."], None),
    ("ruff format --check", [sys.executable, "-m", "ruff", "format", "--check", "."], None),
    (
        "db-test (docker compose --profile test up -d --wait db-test)",
        ["docker", "compose", "--profile", "test", "up", "-d", "--wait", "db-test"],  # noqa: S607
        REPO,
    ),
    ("pytest", [sys.executable, "-m", "pytest"], None),
]


def main() -> int:
    for label, cmd, cwd in STEPS:
        print(f"\n== {label}", flush=True)
        code = subprocess.call(cmd, cwd=cwd)
        if code != 0:
            print(f"\nFALLO: {label}", flush=True)
            return code
    print("\nOK: lint, formato y tests", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
