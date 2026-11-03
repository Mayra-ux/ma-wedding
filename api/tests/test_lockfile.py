"""opentelemetry-api entra como dependencia inerte de FastAPI (ADR 0019).

Ningún SDK ni exportador de OpenTelemetry puede entrar al lock.
"""

import re
from pathlib import Path

LOCK = Path(__file__).resolve().parent.parent / "uv.lock"


def test_no_opentelemetry_sdk_or_exporters() -> None:
    names = re.findall(r'^name = "([^"]+)"', LOCK.read_text(encoding="utf-8"), re.MULTILINE)
    forbidden = [
        n for n in names if n == "opentelemetry-sdk" or n.startswith("opentelemetry-exporter")
    ]
    assert forbidden == []
