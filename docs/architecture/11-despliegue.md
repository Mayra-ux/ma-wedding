# 11. Despliegue portable

Basado en ADR 0002, 0004, 0015, 0019 y 0020. No se elige proveedor: está pendiente.

## Estructura del repositorio (ADR 0020)

| Carpeta | Contenido | Se publica en |
|---|---|---|
| `invitacion/` | `index.html`, imágenes, SVG, `vercel.json`, movidos **sin cambiar un byte** en I-1 | Hosting estático (Root Directory = `invitacion/`) |
| `api/` | Backend FastAPI | Imagen Docker |
| `panel/` | Código fuente React + Vite | Su build va **dentro** de la imagen Docker (ADR 0015) |
| `docs/` | ADRs y arquitectura | No se publica |

Cambiar el Root Directory en Vercel lo hace Mayra, junto con el merge de I-1.

## Una sola imagen

- **Build en varias etapas:** una etapa con Node (`node:24.22.3-slim` fijado por digest) compila el panel; la imagen final solo lleva Python, la API y los archivos estáticos del panel en `/srv/panel` (`PANEL_DIR`). El código del panel entra como contexto adicional `panel-src` (compose: `additional_contexts`; a mano: `docker build --build-context panel-src=panel api`). ADR 0029.
- **Comandos de la misma imagen:**
  - `serve`: API + panel en `/admin/`.
  - `migrate`: con el usuario de migraciones.
  - `purge`: tarea de borrado diaria.
  - `backup`: si el proveedor no ofrece respaldos que cumplan el doc 10.
  - `rotate-keys`: rotación de llaves de tokens (ADR 0019).
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
| `FORWARDED_ALLOW_IPS` | Proxies de confianza para `X-Forwarded-For` (la lee uvicorn; la imagen usa `127.0.0.1`). Se ajusta al elegir proveedor: de ella depende la IP del rate limiting | — |
| `SECURITY_HSTS` | `true` solo con el dominio definitivo (ADR 0019 y 0021); por defecto `false` | — |
| `MAX_BODY_PUBLIC` / `MAX_BODY_ADMIN` / `MAX_IMPORT_FILE` | Tamaños máximos (público: 4096 bytes; panel: 65536) | — |
| `BACKUP_*` | Destino y llave de cifrado de respaldos (si los hace la imagen) | ✔ |
| `ALERT_*` | Canal de alertas de `purge` y `backup` (pendiente) | ✔ |
| `LOG_LEVEL` | Nivel de registro | — |

`PANEL_ORIGIN` volvió en I-6 (decisión aprobada; ADR 0005, notas de implementación) para la URI de redirección de Google y la verificación de `Origin`; el panel sigue en el mismo origen que la API. Ya no hay `PUBLIC_INVITATION_URL` (se deriva de `INVITATION_ORIGIN`). Las fechas (cierre, congelamiento, borrado) viven en la configuración del evento en la DB.

## Enlaces y llaves de tokens (fase I-3)

### Dominio del enlace

El enlace es `INVITATION_ORIGIN + "/#t=" + token` y se arma al consultarlo (se descifra la copia guardada).

| Entorno | `INVITATION_ORIGIN` |
|---|---|
| Local | `http://localhost:8080` |
| Pruebas en la nube | `https://ma-wedding-six.vercel.app` |
| Producción | Dominio definitivo (**pendiente**) |

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

- **PostgreSQL privado**, sin acceso público. Se reevalúa solo al elegir proveedor (ADR 0004, 0019).
- **Dos usuarios:** migraciones (dueño del esquema) y ejecución (solo datos). `purge` usa el de ejecución.
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

## Comparación de opciones de hosting

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
