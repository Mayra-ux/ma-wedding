# Invitación M&A

Invitación digital de la boda de Mayra y Alejandro, con su sistema de confirmación (RSVP).
Arquitectura y decisiones: [docs/architecture/](docs/architecture/) y [docs/adr/](docs/adr/).

## Estructura (ADR 0020)

| Carpeta | Contenido | Se publica en |
|---|---|---|
| `invitacion/` | Sitio estático sin build: `index.html`, `mono-espada.webp`, `mono.webp`, `og.jpg`, `orn-*.svg`, `vercel.json` | Hosting estático (Root Directory = `invitacion`) |
| `api/` | Backend FastAPI (Python 3.12, uv) con su `Dockerfile` | Imagen Docker |
| `panel/` | Panel React + Vite (fase I-9); su build lo sirve la API | Dentro de la imagen de la API |
| `docs/` | ADRs y arquitectura | No se publica |

En la raíz: `compose.yaml` (entorno local), `.env.example` (valores ficticios), `.pre-commit-config.yaml` (escaneo de secretos).

## Ramas

- `main` — versión publicada.
- `develop` — rama de trabajo; los cambios se integran a `main` mediante merge.

## Ver la invitación en local

    cd invitacion
    python -m http.server 8000

y abrir http://localhost:8000.

## API en local

Requisitos: [uv](https://docs.astral.sh/uv/) y Docker Desktop.

    copy .env.example .env                              # PowerShell/cmd; en bash: cp .env.example .env
    docker compose up -d --build                        # API en http://127.0.0.1:8000/health + Postgres 16
    docker compose run --rm migrate                     # esquema (usuario de migraciones)
    docker compose run --rm api python -m app seed-dev  # datos FICTICIOS de desarrollo

La base de datos no publica puertos; para entrar: `docker compose exec db psql -U ma_local ma_wedding_local`.
Nunca uses datos reales en local: `.env` está ignorado por git y solo lleva valores ficticios.

**Llaves de tokens (I-3).** Genera las de tu `.env` local sin mostrarlas:
`cd api && uv run python -m app generar-llaves --env-file ../.env`. Rotación: `docker compose run --rm api python -m app rotate-keys` (procedimiento en el doc 11).
Ningún enlace real se envía a invitados hasta definir el dominio definitivo.

**Dos usuarios de base de datos (ADR 0019).** Al crear el volumen por primera vez, `db/init/01-roles.sh` crea
`ma_migrator` (dueño del esquema; solo lo usa `migrate`) y `ma_app` (solo datos; lo usa la API). Si cambias
esas variables en `.env`, borra el volumen (`docker compose down -v`) para que el script vuelva a correr.

Tests, linter y formato con un solo comando (levanta solo la DB descartable `db-test`, publicada únicamente
en `127.0.0.1:55432` y con los datos en memoria):

    cd api
    uv run python tools/check.py

Para apagarla: `docker compose --profile test down`.

## Escaneo de secretos (una vez por clon)

    uv tool install pre-commit
    pre-commit install

Cada commit pasa por gitleaks y se bloquea si contiene un secreto.

## Despliegue de la invitación

Despliegue provisional en Vercel como sitio estático. Desde el merge de la fase I-1, la invitación vive en
`invitacion/`, por lo que el proyecto de Vercel debe usar:

- **Settings → Build and Deployment → Root Directory:** `invitacion`
- Framework preset "Other", sin build command ni output directory.

Este cambio se hace **en el mismo momento** del merge de I-1 a `main`: antes del merge la carpeta no existe en
`main`; después del merge, sin el cambio, Vercel publicaría la raíz (incluidos `api/` y `docs/`).
