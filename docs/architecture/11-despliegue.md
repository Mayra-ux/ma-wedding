# 11. Despliegue portable

Basado en ADR 0002, 0004, 0015, 0019, 0020 y 0030. **Proveedor decidido para cuando se despliegue: Render** (ADR 0030); en I-10 no se despliega. Paso a paso: [guía de operación](../operacion/guia-despliegue.md).

## Estructura del repositorio (ADR 0020)

| Carpeta | Contenido | Se publica en |
|---|---|---|
| `invitacion/` | `index.html`, imágenes, SVG, `vercel.json`, movidos **sin cambiar un byte** en I-1 | Hosting estático (Root Directory = `invitacion/`) |
| `api/` | Backend FastAPI | Imagen Docker |
| `panel/` | Código fuente React + Vite | Su build va **dentro** de la imagen Docker (ADR 0015) |
| `docs/` | ADRs, arquitectura y guía de operación | No se publica |
| `ops/local/` | Configuración del proxy del modo «como producción» en local (I-10) | No se publica |
| `.github/workflows/` | `imagen.yml`: construye y publica la imagen en GHCR, solo a mano (I-10) | GitHub Actions |

Cambiar el Root Directory en Vercel lo hace Mayra, junto con el merge de I-1.

## Una sola imagen

- **Build en varias etapas:** una etapa con Node (`node:24.22.3-slim` fijado por digest) compila el panel; la imagen final solo lleva Python, la API y los archivos estáticos del panel en `/srv/panel` (`PANEL_DIR`). El código del panel entra como contexto adicional `panel-src` (compose: `additional_contexts`; a mano: `docker build --build-context panel-src=panel api`). ADR 0029.
- **Comandos de la misma imagen:**
  - `serve`: API + panel en `/admin/`.
  - `migrate`: con el usuario de migraciones.
  - `purge`: tarea de borrado diaria (I-10).
  - `backup`: respaldo cifrado diario (I-10; doc 10).
  - `listar-respaldos`, `restaurar` y `verificar-restauracion`: restauración probada (I-10; doc 10).
  - `rotate-keys`: rotación de llaves de tokens (ADR 0019).
- **Herramientas en la imagen (I-10):** `pg_dump`/`pg_restore` 16 (PGDG, llave verificada por huella) y `age` (Debian). Sin compiladores ni curl en la imagen final.
- **Dónde se construye:** Render no admite el contexto adicional `panel-src`, así que la imagen la construye GitHub Actions (`.github/workflows/imagen.yml`, solo manual, acciones fijadas por SHA, procedencia firmada) y la publica en GHCR; Render la descarga fijada por digest (ADR 0030).
- **Endurecimiento (ADR 0019):**
  - Imagen base fijada por digest.
  - Usuario no root.
  - `HEALTHCHECK` contra `/health`.
  - Apagado ordenado con SIGTERM y tiempo de gracia.
  - Sin secretos dentro de la imagen.
- Sin dependencias de servicios propietarios. El programador de tareas y el gestor de secretos del proveedor se usan solo mediante comandos y variables de entorno estándar.

## Variables de entorno

Solo los **nombres** y su propósito. Los valores reales nunca van al repositorio; `.env.example` tendrá valores ficticios (I-1).

| Variable | Propósito | Secreta |
|---|---|:-:|
| `DATABASE_URL` | Conexión con el **usuario de ejecución** (solo datos), TLS obligatorio | ✔ |
| `MIGRATION_DATABASE_URL` | Conexión con el **usuario de migraciones**, solo para `migrate` | ✔ |
| `DB_RUNTIME_ROLE` | Nombre del usuario de ejecución al que `migrate` otorga permisos (por defecto `ma_app`) | — |
| `TOKEN_HASH_KEY` | Llave HMAC-SHA-256 de los tokens: base64url de 32 bytes | ✔ |
| `TOKEN_HASH_KEY_PREVIOUS` | Llave HMAC anterior, **solo durante una rotación** (la búsqueda la prueba después de la actual) | ✔ |
| `TOKEN_ENCRYPTION_KEYS` | Llaves AES-256-GCM `id:base64url32,id:base64url32`; la primera es la actual; `id` ⊂ `[a-z0-9_-]{1,32}` | ✔ |
| `SESSION_SECRET` | Firma de identificadores de sesión y del estado de OAuth: base64url de 32 bytes o más; lo escribe `generar-llaves --env-file` | ✔ |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Cliente OAuth de Google | — / ✔ |
| `ADMIN_EMAILS_NOVIOS` / `ADMIN_EMAILS_PLANNER` | Listas de correos por rol, separadas por comas; un correo no puede estar en ambas | ✔ (no exponer) |
| `PANEL_ORIGIN` | Origen público de la API y del panel (I-6): base de la URI de redirección de Google (`<PANEL_ORIGIN>/api/v1/auth/google/callback`) y valor esperado de `Origin` en las escrituras. `https` salvo localhost; por defecto `http://localhost:8000` | — |
| `PANEL_DIR` | Carpeta del build del panel (I-9). La imagen la fija en `/srv/panel`; sin build, `/admin/` responde 503 | — |
| `SESION_INACTIVIDAD_HORAS` / `SESION_MAXIMA_DIAS` | Cierre de la sesión del panel: 8 h sin actividad / 7 días como máximo | — |
| `INVITATION_ORIGIN` | Origen de la invitación: CORS de la API pública y base del enlace `/#t=`. Solo esquema y host; `https` salvo `localhost`/`127.0.0.1` | — |
| `RATE_LIMIT_TOKEN_LOOKUP_PER_HOUR` / `RATE_LIMIT_TOKEN_RESPONSE_PER_HOUR` / `RATE_LIMIT_IP_PER_HOUR` | Umbrales (ADR 0019): 20 / 10 / 300 por hora | — |
| `TRUSTED_PROXY_HOPS` | Número de proxies delante de la API que agregan la IP del cliente a `X-Forwarded-For` (I-10, ADR 0030). La IP del cliente es la N-ésima **desde la derecha**; 0 = la IP de la conexión. Render: `1`. Reemplaza a `FORWARDED_ALLOW_IPS` (uvicorn corre con `--no-proxy-headers`) | — |
| `SECURITY_HSTS` | `true` solo con el dominio definitivo (ADR 0019 y 0021); por defecto `false` | — |
| `MAX_BODY_PUBLIC` / `MAX_BODY_ADMIN` / `MAX_IMPORT_FILE` | Tamaños máximos (público: 4096 bytes; panel: 65536) | — |
| `BACKUP_DIR` | Destino de respaldos en una carpeta (local) **o** bien `BACKUP_S3_*` | — |
| `BACKUP_S3_ENDPOINT` / `BACKUP_S3_BUCKET` / `BACKUP_S3_REGION` | Almacenamiento S3 compatible (R2: `https://<cuenta>.r2.cloudflarestorage.com`, región `auto`) | — |
| `BACKUP_S3_ACCESS_KEY_ID` / `BACKUP_S3_SECRET_ACCESS_KEY` | Token de R2 con acceso **solo a ese bucket** | ✔ |
| `BACKUP_AGE_RECIPIENT` | Llave **pública** de age (`age1…`); la privada nunca va al proveedor | — |
| `ALERT_PING_URL_BACKUP` / `ALERT_PING_URL_PURGE` | URL de ping de Healthchecks por tarea; vacía = alertas apagadas | ✔ |
| `LOG_LEVEL` | Nivel de registro | — |

`PANEL_ORIGIN` volvió en I-6 (decisión aprobada; ADR 0005, notas de implementación) para la URI de redirección de Google y la verificación de `Origin`; el panel sigue en el mismo origen que la API. Ya no hay `PUBLIC_INVITATION_URL` (se deriva de `INVITATION_ORIGIN`). Las fechas (cierre, congelamiento, borrado) viven en la configuración del evento en la DB.

## Enlaces y llaves de tokens (fase I-3)

### Dominio del enlace

El enlace es `INVITATION_ORIGIN + "/#t=" + token` y se arma al consultarlo (se descifra la copia guardada).

| Entorno | `INVITATION_ORIGIN` |
|---|---|
| Local | `http://localhost:8080` |
| Pruebas en la nube | `https://ma-wedding-six.vercel.app` |
| Producción | `https://<dominio>` (`.com` en Cloudflare, invitación en Vercel; ADR 0030). La compra está pendiente |

> **Regla (ADR 0021): NINGÚN enlace real se envía a invitados hasta definir el dominio definitivo.** El dominio queda escrito dentro de cada enlace enviado por WhatsApp; si después cambia, los enlaces ya enviados seguirían apuntando al dominio anterior. Con el dominio de pruebas solo se usan invitaciones ficticias.

### Llaves

- **Generar** (local o para un entorno nuevo): `cd api && uv run python -m app generar-llaves --env-file ../.env` escribe `TOKEN_HASH_KEY` y `TOKEN_ENCRYPTION_KEYS` en el archivo **sin imprimirlas** y se niega a pisar llaves existentes. Sin `--env-file` las imprime, para copiarlas al gestor de secretos del proveedor.
- Las llaves nunca van al repositorio; `.env.example` solo tiene `__GENERAR__`.
- Si se pierde la llave de cifrado, los enlaces no se pueden volver a mostrar: hay que regenerarlos y reenviarlos (ADR 0008). Si se pierde la de hash, los enlaces enviados dejan de funcionar.

### Rotación (`rotate-keys`, ADR 0019 y 0022)

1. Poner la llave de cifrado nueva **al principio** de `TOKEN_ENCRYPTION_KEYS`, conservando la anterior. Si también se rota la de hash: la nueva en `TOKEN_HASH_KEY` y la anterior en `TOKEN_HASH_KEY_PREVIOUS`. Reiniciar la API (los enlaces siguen funcionando: la búsqueda prueba ambas llaves de hash).
2. Ejecutar `python -m app rotate-keys` (misma imagen, usuario de ejecución). En una transacción, con las filas bloqueadas, descifra **cada** copia (también las revocadas), la vuelve a cifrar con la llave actual y recalcula el HMAC. Es idempotente y solo imprime conteos. Si una copia no se puede descifrar, no cambia nada.
3. Si terminó sin errores, quitar la llave anterior y `TOKEN_HASH_KEY_PREVIOUS`, y reiniciar.

## Base de datos

- **PostgreSQL 16 privado**, sin acceso público (en Render: lista de IPs vacía; conexión interna con `sslmode=require`). ADR 0004, 0019 y 0030.
- **Dos usuarios:** migraciones (dueño del esquema) y ejecución (solo datos, más lectura de `alembic_version` y las secuencias para `pg_dump`, migración 0006). `purge` y `backup` usan el de ejecución; `restaurar` usa el de migraciones de la base **nueva**.
- **TLS obligatorio**, con verificación de certificado si el proveedor lo permite.
- Mover de proveedor: volcado lógico + restauración (doc 10) + `migrate`.
- **Crear los usuarios en el proveedor** (equivale a `db/init/01-roles.sh` del entorno local; contraseñas largas y aleatorias en el gestor de secretos, nunca en el repo):

  ```sql
  CREATE ROLE ma_migrator LOGIN PASSWORD '<secreto>' NOSUPERUSER NOCREATEDB NOCREATEROLE;
  CREATE ROLE ma_app      LOGIN PASSWORD '<secreto>' NOSUPERUSER NOCREATEDB NOCREATEROLE;
  ALTER DATABASE <base> OWNER TO ma_migrator;
  REVOKE ALL ON DATABASE <base> FROM PUBLIC;
  GRANT CONNECT ON DATABASE <base> TO ma_migrator, ma_app;
  ```

  Después, `migrate` (con `MIGRATION_DATABASE_URL` y `DB_RUNTIME_ROLE=ma_app`) crea el esquema y otorga a `ma_app` solo permisos de datos (doc 02, «Usuarios de la DB»).

## Comparación de opciones de hosting (antes de elegir)

La elección quedó en el ADR 0030 (Render). Se conserva la comparación general:

| Criterio | VPS | PaaS de contenedores (**ADR 0004**) | Contenedores serverless |
|---|---|---|---|
| Mantenimiento | Alto: sistema operativo, parches, firewall, TLS | Bajo | Muy bajo |
| Costo para este volumen | Bajo y fijo | Bajo a medio | Muy bajo, por uso |
| Arranque en frío | No | No, con una instancia encendida | **Sí**: la primera petición tras inactividad tarda segundos |
| Tareas programadas | Cron propio | Suele incluirlo | Programador del proveedor o externo |
| Red privada hacia la DB | Manual | Suele incluirla | Variable |
| Rate limiting en memoria | Sí | Sí (una instancia) | **No**: las instancias son efímeras; requeriría la DB |
| Control de logs | Total | Hay que confirmar retención o filtrado | Medio |
| Portabilidad | Total | Alta (Docker) | Alta (Docker) |

**Requisitos mínimos del proveedor:**
- Imagen Docker estándar con una instancia persistente.
- Postgres privado con TLS y dos usuarios.
- Programador de tareas.
- Gestor de secretos.
- Logs con retención corta o filtrables.
- Respaldos con vencimiento por fecha absoluta.
- Un canal para alertas.

## Entornos

| Entorno | Datos | Uso |
|---|---|---|
| Local | Ficticios, Postgres en contenedor | Desarrollo (I-1 en adelante) |
| Pruebas | Ficticios | Despliegue, restauración y prueba del fragmento en WhatsApp |
| Producción | Reales | Solo tras aprobar I-5, el aviso de privacidad y la lista de salida de I-10 |

## Login con Google (fase I-6)

- El cliente OAuth lo crea Mayra en Google Cloud: tipo **Aplicación web**, pantalla de consentimiento **Externa** en modo **Prueba** con los correos autorizados como usuarios de prueba, y solo los alcances `openid` y `email`.
- **Un cliente por entorno.** Local: URI de redirección `http://localhost:8000/api/v1/auth/google/callback`. Producción (I-10): `<PANEL_ORIGIN>/api/v1/auth/google/callback` con el dominio de la API.
- El secreto del cliente solo se escribe en las variables de entorno, nunca en el repo.
- En local, las cookies `Secure` y `__Host-` funcionan en `http://localhost` con Chrome o Edge; Safari no las acepta en http.
- Después de cambiar las listas de correos hay que recrear el contenedor (`docker compose up -d --force-recreate api`): las listas se leen al arrancar.
