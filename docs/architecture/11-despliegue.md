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

- **Build en varias etapas:** una etapa con Node compila el panel; la imagen final solo lleva Python, la API y los archivos estáticos del panel.
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
| `TOKEN_HASH_KEY` | Llave HMAC-SHA-256 de los tokens | ✔ |
| `TOKEN_ENCRYPTION_KEYS` | Llaves AES-256-GCM con identificador; la primera es la actual (rotación) | ✔ |
| `SESSION_SECRET` | Firma de identificadores de sesión y del estado de OAuth | ✔ |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Cliente OAuth de Google | — / ✔ |
| `ADMIN_EMAILS_NOVIOS` / `ADMIN_EMAILS_PLANNER` | Listas de correos por rol | ✔ (no exponer) |
| `INVITATION_ORIGIN` | Origen de la invitación: CORS de la API pública y base del enlace `/#t=` | — |
| `RATE_LIMIT_TOKEN_*` / `RATE_LIMIT_IP_*` | Umbrales (ADR 0019) | — |
| `MAX_BODY_PUBLIC` / `MAX_BODY_ADMIN` / `MAX_IMPORT_FILE` | Tamaños máximos | — |
| `BACKUP_*` | Destino y llave de cifrado de respaldos (si los hace la imagen) | ✔ |
| `ALERT_*` | Canal de alertas de `purge` y `backup` (pendiente) | ✔ |
| `LOG_LEVEL` | Nivel de registro | — |

Ya no hay `PANEL_ORIGIN` (el panel es el mismo origen) ni `PUBLIC_INVITATION_URL` (se deriva de `INVITATION_ORIGIN`). Las fechas (cierre, congelamiento, borrado) viven en la configuración del evento en la DB.

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
