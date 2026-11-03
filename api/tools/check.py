"""Un solo comando para lint + formato + tests: `uv run python tools/check.py`."""

import subprocess
import sys

STEPS = [
    ("ruff check", [sys.executable, "-m", "ruff", "check", "."]),
    ("ruff format --check", [sys.executable, "-m", "ruff", "format", "--check", "."]),
    ("pytest", [sys.executable, "-m", "pytest"]),
]


def main() -> int:
    for label, cmd in STEPS:
        print(f"\n== {label}", flush=True)
        code = subprocess.call(cmd)
        if code != 0:
            print(f"\nFALLO: {label}", flush=True)
            return code
    print("\nOK: lint, formato y tests", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
