"""Comandos de la imagen (`python -m app …`): migrate, seed-dev, generar-llaves, rotate-keys,
purge, backup, listar-respaldos, restaurar y verificar-restauracion (I-10)."""

import argparse
import sys
from pathlib import Path

from sqlalchemy.exc import OperationalError

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


def claves_con_valor(ruta: Path) -> set[str]:
    """Variables del .env que ya tienen un valor real (no vacío ni marcador)."""
    if not ruta.exists():
        return set()
    con_valor = set()
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        clave, sep, valor = linea.partition("=")
        if sep and not clave.lstrip().startswith("#") and valor.strip() not in ("", MARCADOR):
            con_valor.add(clave.strip())
    return con_valor


def _generar_llaves(env_file: str | None, reemplazar: bool) -> int:
    from app.sesiones_panel import generar_secreto_sesion
    from app.tokens import generar_llaves_env

    valores = generar_llaves_env() | {"SESSION_SECRET": generar_secreto_sesion()}
    if env_file:
        ruta = Path(env_file)
        # Sin --reemplazar solo se llenan las que faltan: nunca se pisan llaves existentes.
        existentes = set() if reemplazar else claves_con_valor(ruta) & set(valores)
        nuevas = {k: v for k, v in valores.items() if k not in existentes}
        if nuevas:
            escribir_en_env(ruta, nuevas, reemplazar)
        print(
            f"generar-llaves: escritas en {env_file}: {', '.join(nuevas) or 'ninguna'}"
            f"{'; ya existían: ' + ', '.join(sorted(existentes)) if existentes else ''}"
            " (valores no mostrados)."
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


def _purge() -> int:
    from sqlalchemy.orm import Session

    from app.alertas import Alerta
    from app.db import make_engine
    from app.estado import reloj_sistema
    from app.purga import purgar

    settings = get_settings()
    alerta = Alerta(_secreto(settings.alert_ping_url_purge))
    alerta.inicio()
    if not settings.database_url:
        alerta.fallo("configuración", "falta DATABASE_URL")
        print("Falta DATABASE_URL (usuario de ejecución).", file=sys.stderr)
        return 2
    try:
        engine = make_engine(settings.database_url)
        with Session(engine) as s, s.begin():
            informe = purgar(s, reloj_sistema)
        engine.dispose()
    except Exception as exc:  # noqa: BLE001  (se avisa y se sale con error)
        alerta.fallo("purge", type(exc).__name__)
        print(f"purge: FALLÓ ({type(exc).__name__}); no se aplicó ningún cambio.", file=sys.stderr)
        return 1
    print(informe.texto())
    alerta.exito(informe.texto())
    return 0


def _secreto(valor) -> str | None:  # noqa: ANN001
    return valor.get_secret_value() if valor else None


def _backup() -> int:
    from app.alertas import Alerta
    from app.db import make_engine
    from app.estado import reloj_sistema
    from app.respaldo import ErrorRespaldo, destino_desde, respaldar

    settings = get_settings()
    alerta = Alerta(_secreto(settings.alert_ping_url_backup))
    alerta.inicio()
    try:
        if not settings.database_url:
            raise ErrorRespaldo("configuración", "falta DATABASE_URL")
        destino = destino_desde(settings)
        engine = make_engine(settings.database_url)
        try:
            informe = respaldar(
                engine,
                settings.database_url,
                destino,
                settings.backup_age_recipient,
                reloj_sistema,
            )
        finally:
            engine.dispose()
    except ErrorRespaldo as exc:
        alerta.fallo(exc.paso, str(exc))
        print(f"backup: FALLÓ en {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        alerta.fallo("backup", type(exc).__name__)
        print(f"backup: FALLÓ ({type(exc).__name__})", file=sys.stderr)
        return 1
    print(informe.texto())
    alerta.exito(informe.texto())
    return 0


def _listar_respaldos() -> int:
    from app.respaldo import PREFIJO, destino_desde

    for clave in destino_desde(get_settings()).listar(PREFIJO):
        print(clave)
    return 0


_SIN_BASE = "{cmd}: FALLÓ: no se pudo conectar a la base (¿existe y es la correcta?)."


def _restaurar(clave: str, identidad: str) -> int:
    from app.db import make_engine
    from app.respaldo import ErrorRespaldo, destino_desde, restaurar

    settings = get_settings()
    if not settings.migration_database_url:
        print("Falta MIGRATION_DATABASE_URL de la base NUEVA (usuario dueño).", file=sys.stderr)
        return 2
    engine = make_engine(settings.migration_database_url)
    try:
        restaurar(
            engine, settings.migration_database_url, destino_desde(settings), clave, Path(identidad)
        )
    except ErrorRespaldo as exc:
        print(f"restaurar: FALLÓ en {exc}", file=sys.stderr)
        return 1
    except OperationalError:
        print(_SIN_BASE.format(cmd="restaurar"), file=sys.stderr)
        return 1
    except (FileNotFoundError, KeyError):
        print(f"restaurar: no existe el respaldo {clave} (listar-respaldos).", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print(f"restaurar: {clave} cargado. Siguiente paso: verificar-restauracion --clave {clave}")
    return 0


def _verificar_restauracion(clave: str) -> int:
    import json

    from app.db import make_engine
    from app.estado import reloj_sistema
    from app.respaldo import clave_informe, destino_desde, verificar_restauracion

    settings = get_settings()
    if not settings.database_url:
        print("Falta DATABASE_URL (usuario de ejecución de la base restaurada).", file=sys.stderr)
        return 2
    try:
        informe_respaldo = json.loads(destino_desde(settings).bajar(clave_informe(clave)))
    except FileNotFoundError:
        print(f"verificar-restauracion: no existe el respaldo {clave}.", file=sys.stderr)
        return 1
    engine = make_engine(settings.database_url)
    try:
        informe = verificar_restauracion(engine, informe_respaldo, reloj_sistema)
    except OperationalError:
        print(_SIN_BASE.format(cmd="verificar-restauracion"), file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print(informe.texto())
    return 0 if informe.correcta else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="Aplica las migraciones (usuario de migraciones).")
    sub.add_parser("seed-dev", help="Carga datos ficticios de desarrollo.")
    gen = sub.add_parser("generar-llaves", help="Genera llaves de tokens y SESSION_SECRET.")
    gen.add_argument("--env-file", help="Escribe en este .env en vez de imprimir.")
    gen.add_argument(
        "--reemplazar", action="store_true", help="Solo local: pisa llaves existentes."
    )
    sub.add_parser("rotate-keys", help="Vuelve a cifrar los enlaces con la llave actual.")
    sub.add_parser("purge", help="Borrado programado de datos personales (diario).")
    sub.add_parser("backup", help="Respaldo cifrado al destino configurado (diario).")
    sub.add_parser("listar-respaldos", help="Lista los respaldos del destino.")
    rest = sub.add_parser("restaurar", help="Carga un respaldo en una base NUEVA y vacía.")
    rest.add_argument("--clave", required=True, help="Clave del respaldo (listar-respaldos).")
    rest.add_argument("--identidad", required=True, help="Archivo con la llave PRIVADA de age.")
    ver = sub.add_parser("verificar-restauracion", help="Purga y compara conteos (F9).")
    ver.add_argument("--clave", required=True, help="Clave del respaldo restaurado.")
    args = parser.parse_args(argv)
    if args.cmd == "generar-llaves":
        return _generar_llaves(args.env_file, args.reemplazar)
    if args.cmd == "restaurar":
        return _restaurar(args.clave, args.identidad)
    if args.cmd == "verificar-restauracion":
        return _verificar_restauracion(args.clave)
    return {
        "migrate": _migrate,
        "seed-dev": _seed_dev,
        "rotate-keys": _rotate_keys,
        "purge": _purge,
        "backup": _backup,
        "listar-respaldos": _listar_respaldos,
    }[args.cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
