"""Prueba en vivo del límite por IP detrás del proxy (modo «como producción», I-10).

    uv run python tools/probar_proxy.py [--url http://127.0.0.1:8000]

Envía 301 peticiones a la API pública con un `X-Forwarded-For` falso y distinto en cada una
(lo que haría un atacante). El proxy agrega la IP real a la derecha y la API la usa: la 301
debe recibir 429. Solo usa la biblioteca estándar y no envía ningún token ni dato personal.

Ojo: después de correrlo, tu IP queda limitada en la API pública durante una hora (hasta
reiniciar el contenedor: `docker compose --profile prod-local restart api-prod`).
"""

import argparse
import json
import secrets
import urllib.error
import urllib.request


def peticion(url: str) -> int:
    falsa = f"198.51.100.{secrets.randbelow(254) + 1}"
    req = urllib.request.Request(  # noqa: S310  (URL local de prueba)
        url + "/api/v1/public/invitation/lookup",
        data=json.dumps({}).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "X-Forwarded-For": falsa},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code


def main() -> int:
    parser = argparse.ArgumentParser()
    # 127.0.0.1 y no localhost: en Windows, localhost prueba IPv6 primero y cada petición tarda.
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--limite", type=int, default=300)
    args = parser.parse_args()
    codigos = [peticion(args.url) for _ in range(args.limite + 1)]
    antes = sorted(set(codigos[: args.limite]))
    print(f"peticiones 1–{args.limite}: códigos {antes}")
    print(f"petición {args.limite + 1}: {codigos[-1]}")
    ok = 429 not in codigos[: args.limite] and codigos[-1] == 429
    print("OK: el encabezado falsificado no evade el límite" if ok else "FALLO")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
