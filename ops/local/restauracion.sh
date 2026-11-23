#!/bin/sh
# Prueba de restauración del modo «como producción» (I-10; docs/operacion/modo-como-produccion.md).
# Se ejecuta DENTRO de los contenedores; arma las URLs con las variables del .env del contenedor,
# así que en PowerShell no se escriben contraseñas ni comillas anidadas.
#   crear <base>              (en db-prod)      base nueva y vacía, dueña: usuario de migraciones
#   restaurar <base> <clave>  (en tareas-prod)  pg_restore con la llave privada en /run/llave.txt
#   verificar <base> <clave>  (en tareas-prod)  purga + comparación de conteos
#   borrar <base>             (en db-prod)
set -eu

accion="${1:-}"
base="${2:-}"
case "$base" in
  ma_restaurada|ma_restaurada_*) ;;
  *) echo "La base debe llamarse ma_restaurada (o ma_restaurada_<algo>)." >&2; exit 2 ;;
esac

case "$accion" in
  crear)
    psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
      -c "CREATE DATABASE $base OWNER $DB_MIGRATOR_USER" \
      -c "REVOKE ALL ON DATABASE $base FROM PUBLIC" \
      -c "GRANT CONNECT ON DATABASE $base TO $DB_MIGRATOR_USER, $DB_RUNTIME_ROLE"
    echo "Base $base creada (vacía)."
    ;;
  borrar)
    psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
      -c "DROP DATABASE IF EXISTS $base WITH (FORCE)"
    echo "Base $base borrada."
    ;;
  restaurar)
    MIGRATION_DATABASE_URL="postgresql+psycopg://$DB_MIGRATOR_USER:$DB_MIGRATOR_PASSWORD@db-prod:5432/$base" \
      exec python -m app restaurar --clave "$3" --identidad /run/llave.txt
    ;;
  verificar)
    DATABASE_URL="postgresql+psycopg://$DB_RUNTIME_ROLE:$DB_APP_PASSWORD@db-prod:5432/$base" \
      exec python -m app verificar-restauracion --clave "$3"
    ;;
  *)
    echo "Uso: restauracion.sh crear|restaurar|verificar|borrar <base> [clave]" >&2
    exit 2
    ;;
esac
