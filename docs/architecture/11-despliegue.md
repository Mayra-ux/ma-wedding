# 11. Despliegue portable

Basado en ADR 0002 y 0004. No se elige proveedor: está pendiente.

## Una sola imagen

- La API FastAPI se empaqueta en **una imagen Docker** que corre igual en local, en pruebas y en producción.
- Esa misma imagen expone varios comandos:
  - `serve`: la API.
  - `migrate`: aplica cambios de esquema al desplegar.
  - `purge`: tarea de borrado diaria (ADR 0010).
  - `backup`: volcado cifrado, si el hosting no ofrece un mecanismo propio que cumpla [10-respaldos.md](10-respaldos.md).
- La invitación y el panel son archivos estáticos que se publican en cualquier hosting estático (hoy, la invitación en Vercel de forma provisional).
- Sin dependencias de servicios propietarios: lo que necesite el proveedor (programador de tareas, gestor de secretos) se usa solo a través de comandos y variables de entorno estándar.

## Variables de entorno

Solo los **nombres** y su propósito; los valores reales nunca van al repositorio (`.env.example` tendrá valores ficticios cuando se autorice crearlo).

| Variable | Propósito | Secreta |
|---|---|:-:|
| `DATABASE_URL` | Conexión a PostgreSQL con el usuario de privilegios mínimos | ✔ |
| `TOKEN_ENCRYPTION_KEY` | Llave para la copia cifrada de los tokens (ADR 0008) | ✔ |
| `SESSION_SECRET` | Firma de los identificadores de sesión y del estado de OAuth | ✔ |
| `GOOGLE_CLIENT_ID` | Cliente OAuth de Google | — |
| `GOOGLE_CLIENT_SECRET` | Secreto del cliente OAuth | ✔ |
| `ADMIN_EMAILS_NOVIOS` | Lista de correos con rol novios | ✔ (no exponer) |
| `ADMIN_EMAILS_PLANNER` | Lista de correos con rol planner | ✔ (no exponer) |
| `INVITATION_ORIGIN` | Origen de la invitación (CORS y formato del enlace) | — |
| `PANEL_ORIGIN` | Origen del panel (CORS con credenciales, redirecciones de login) | — |
| `PUBLIC_INVITATION_URL` | Base del enlace `https://[dominio]/#t=` | — |
| `RATE_LIMIT_*` | Umbrales de rate limiting | — |
| `BACKUP_*` | Destino y llave de cifrado de respaldos (si los hace la imagen) | ✔ |
| `LOG_LEVEL` | Nivel de registro | — |

La fecha límite y las fechas de borrado viven en la configuración del evento, en la base de datos (ADR 0007), no en variables de entorno.

## Comparación de opciones de hosting

| Criterio | VPS | PaaS de contenedores (**elegido en ADR 0004**) | Contenedores serverless |
|---|---|---|---|
| Mantenimiento | Alto: sistema operativo, parches, firewall, TLS, monitoreo | Bajo: el proveedor gestiona el servidor y el TLS | Muy bajo |
| Costo para este volumen | Bajo y fijo | Bajo a medio, normalmente fijo | Muy bajo; se paga por uso |
| Arranque en frío | No | No, si la instancia queda encendida | **Sí**: la primera petición tras un periodo inactivo tarda segundos. Afecta a la experiencia del invitado |
| Tareas programadas (`purge`, `backup`) | Cron propio | Suele incluir un programador | Requiere el programador del proveedor o uno externo |
| Red privada hacia la DB | Hay que configurarla a mano | Suele incluirla con su Postgres o mediante red privada | Variable; a veces exige conectores |
| Control de logs | Total | Medio: hay que confirmar que se puede filtrar o retener poco tiempo | Medio |
| Rate limiting | En memoria basta (una instancia) | En memoria si hay una sola instancia; si escala, en la DB | Necesita un almacén compartido (DB), porque cada instancia es efímera |
| Portabilidad | Total | Alta, con la imagen Docker | Alta, con la imagen Docker |
| Respaldos fuera del proveedor | Manuales | Manuales o con tarea programada | Manuales o con tarea programada |

Requisitos mínimos para el proveedor que se elija:
- Correr una imagen Docker estándar.
- Postgres sin acceso público.
- Programador de tareas.
- Gestor de secretos.
- Logs con retención corta o filtrables.
- Respaldos con vencimiento por fecha absoluta.

## Entornos

| Entorno | Datos | Uso |
|---|---|---|
| Local | Ficticios, en un Postgres local en contenedor | Desarrollo |
| Pruebas | Ficticios | Verificar el despliegue, la restauración y los navegadores de WhatsApp con enlaces de prueba |
| Producción | Reales | Solo después de aprobar I-5 y el aviso de privacidad |

Ningún entorno distinto de producción contiene datos reales (ADR 0010).
