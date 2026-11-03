"""Comandos de la imagen: migrate, seed-dev, generar-llaves y rotate-keys (`python -m app …`)."""

import argparse
import sys
from pathlib import Path

from app.config import get_settings


def _migrate() -> int:
    from app import migrar

    settings = get_settings()
    if not settings.migration_database_url:
        print("Falta MIGRATION_DATABASE_URL (usuario de migraciones).", file=sys.stderr)
        return 2
    migrar.upgrade(settings.migration_database_url, settings.db_runtime_role)
    print("migrate: esquema en la última versión.")
    return 0


def _seed_dev() -> int:
    from app.db import make_engine, make_sessionmaker
    from app.seed import seed

    settings = get_settings()
    if not settings.database_url:
        print("Falta DATABASE_URL (usuario de ejecución).", file=sys.stderr)
        return 2
    engine = make_engine(settings.database_url)
    with make_sessionmaker(engine).begin() as session:
        n = seed(session)
    engine.dispose()
    print(f"seed-dev: {n} invitaciones ficticias creadas.")
    return 0


MARCADOR = "__GENERAR__"


def escribir_en_env(ruta: Path, valores: dict[str, str], reemplazar: bool) -> None:
    """Escribe las variables en un archivo .env sin imprimir sus valores.

    Reemplaza `CLAVE=__GENERAR__` (o vacía). Si ya hay una llave real, se niega salvo
    `reemplazar`, porque cambiar llaves sin `rotate-keys` rompe los enlaces existentes.
    """
    lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    pendientes = dict(valores)
    for i, linea in enumerate(lineas):
        clave, sep, actual = linea.partition("=")
        clave = clave.strip()
        if sep and clave in pendientes:
            if actual.strip() not in ("", MARCADOR) and not reemplazar:
                raise SystemExit(
                    f"{ruta}: {clave} ya tiene una llave. No se cambió nada. "
                    "Para rotar llaves usa rotate-keys (ver doc 11); --reemplazar solo en local."
                )
            lineas[i] = f"{clave}={pendientes.pop(clave)}"
    lineas += [f"{k}={v}" for k, v in pendientes.items()]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def _generar_llaves(env_file: str | None, reemplazar: bool) -> int:
    from app.tokens import generar_llaves_env

    valores = generar_llaves_env()
    if env_file:
        escribir_en_env(Path(env_file), valores, reemplazar)
        print(
            f"generar-llaves: {', '.join(valores)} escritas en {env_file} (valores no mostrados)."
        )
    else:
        for clave, valor in valores.items():
            print(f"{clave}={valor}")
    return 0


def _rotate_keys() -> int:
    from app.db import make_engine, make_sessionmaker
    from app.enlaces import rotar_llaves

    settings = get_settings()
    if not settings.database_url:
        print("Falta DATABASE_URL (usuario de ejecución).", file=sys.stderr)
        return 2
    llaves = settings.llaves()
    engine = make_engine(settings.database_url)
    with make_sessionmaker(engine).begin() as session:
        informe = rotar_llaves(session, llaves)
    engine.dispose()
    print(
        f"rotate-keys: enlaces {informe.enlaces} · recifrados {informe.recifrados} · "
        f"ya al día {informe.al_dia} · llave actual '{llaves.id_actual}'."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="Aplica las migraciones (usuario de migraciones).")
    sub.add_parser("seed-dev", help="Carga datos ficticios de desarrollo.")
    gen = sub.add_parser("generar-llaves", help="Genera llaves nuevas de tokens.")
    gen.add_argument("--env-file", help="Escribe en este .env en vez de imprimir.")
    gen.add_argument(
        "--reemplazar", action="store_true", help="Solo local: pisa llaves existentes."
    )
    sub.add_parser("rotate-keys", help="Vuelve a cifrar los enlaces con la llave actual.")
    args = parser.parse_args(argv)
    if args.cmd == "generar-llaves":
        return _generar_llaves(args.env_file, args.reemplazar)
    return {"migrate": _migrate, "seed-dev": _seed_dev, "rotate-keys": _rotate_keys}[args.cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
