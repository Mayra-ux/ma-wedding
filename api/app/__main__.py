"""Comandos de la imagen: `python -m app migrate` y `python -m app seed-dev`."""

import argparse
import sys

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="Aplica las migraciones (usuario de migraciones).")
    sub.add_parser("seed-dev", help="Carga datos ficticios de desarrollo.")
    args = parser.parse_args(argv)
    return {"migrate": _migrate, "seed-dev": _seed_dev}[args.cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
