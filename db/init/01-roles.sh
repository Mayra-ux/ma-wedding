#!/bin/sh
# Solo para el Postgres LOCAL de compose (se ejecuta una vez, con el volumen vacío).
# Crea los dos usuarios de ADR 0019 con contraseñas FICTICIAS de .env:
#   - migraciones: dueño de la base (y por tanto del esquema public); solo `migrate`.
#   - ejecución:   solo CONNECT; la migración 0001 le otorga permisos de datos.
# En producción el equivalente se ejecuta a mano (ver docs/architecture/11-despliegue.md).
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v migrator="$DB_MIGRATOR_USER" -v migrator_pw="$DB_MIGRATOR_PASSWORD" \
  -v app="$DB_RUNTIME_ROLE" -v app_pw="$DB_APP_PASSWORD" \
  -v db="$POSTGRES_DB" <<'SQL'
CREATE ROLE :"migrator" LOGIN PASSWORD :'migrator_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE :"app" LOGIN PASSWORD :'app_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE;
ALTER DATABASE :"db" OWNER TO :"migrator";
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO :"migrator", :"app";
SQL
