# Invitación M&A

Invitación digital de la boda de Mayra y Alejandro, con su sistema de confirmación (RSVP).
Arquitectura y decisiones: [docs/architecture/](docs/architecture/) y [docs/adr/](docs/adr/).

## Estructura (ADR 0020)

| Carpeta | Contenido | Se publica en |
|---|---|---|
| `invitacion/` | Sitio estático sin build: `index.html`, `mono-espada.webp`, `mono.webp`, `og.jpg`, `orn-*.svg`, `vercel.json` | Hosting estático (Root Directory = `invitacion`) |
| `api/` | Backend FastAPI (Python 3.12, uv) con su `Dockerfile` | Imagen Docker |
| `panel/` | Panel React + Vite (I-9); su build lo sirve la API en `/admin/` | Dentro de la imagen de la API |
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

**Invitación conectada (I-5):** la URL de la API se configura en `<meta name="api-base">` de `invitacion/index.html`; después corre `cd api && uv run python tools/csp_invitacion.py --actualizar` para recalcular la CSP. I-5 solo vive en `develop` hasta cumplir las condiciones del ADR 0024.

**Panel y login con Google (I-6):** la API sirve una página provisional en http://localhost:8000/admin/ (Chrome o Edge). Necesita en `.env`: `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` (cliente OAuth "Aplicación web" con la URI `http://localhost:8000/api/v1/auth/google/callback`), `ADMIN_EMAILS_NOVIOS`, `ADMIN_EMAILS_PLANNER` y `SESSION_SECRET` (lo escribe `generar-llaves --env-file ../.env` sin mostrarlo). Tras cambiar el `.env`: `docker compose up -d --force-recreate api`. Detalle en el doc 11.

**Importación y exportación (I-8, ADR 0028):** los novios importan el Excel (.xlsx) o un CSV de la planner desde el panel, eligiendo la hoja y el lado por defecto; la vista previa no guarda nada y aplicar es todo o nada. **Regla de trabajo:** cada hoja de la planner se importa una sola vez (su archivo no trae Código INV, así que reimportarla duplicaría invitaciones); después, los cambios se hacen en el panel o reimportando el archivo exportado, que sí trae Código INV. La exportación (novios y planner) tiene 19 columnas, teléfonos E.164 y la opción `solo_confirmados`, útil para el script del mensaje del día de la boda. **Los archivos exportados contienen teléfonos y alergias:** guárdalos fuera del repo (`*.xlsx` y `*.csv` están ignorados) y bórralos o recórtalos el 5 abr 2027 (ADR 0010). Las pruebas usan solo archivos ficticios generados en `api/tests/planilla_ficticia.py`.

**Panel (I-9, ADR 0029):** abre `http://localhost:8000/admin/` con la API levantada (`docker compose up -d --build`). Novios y planner entran con Google; la planner no ve enlaces ni botones de escritura salvo marcar recordatorios. No necesitas Node: `uv run python tools/check.py` compila y prueba el panel dentro del contenedor `node:24.22.3`, y `--e2e` corre la prueba de punta a punta con tu Chrome o Edge. El panel cierra la sesión a los 30 minutos sin uso. Detalle en `panel/README.md`.

**API pública (I-4):** `POST /api/v1/public/invitation/lookup` y `POST /api/v1/public/invitation/response`, con el token en el cuerpo. Contrato y códigos de error: doc 07.

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
