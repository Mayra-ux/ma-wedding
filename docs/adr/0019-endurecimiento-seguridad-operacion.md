# ADR 0019 — Endurecimiento de seguridad y operación

- **Estado:** Aceptado
- **Fecha:** 2026-11-02
- **Complementa:** ADR 0004, 0005, 0008, 0010 y 0015 (no reemplaza ninguna decisión; las precisa)

## Contexto

La validación de la Fase 3 encontró huecos de seguridad y operación: encabezados HTTP, algoritmos del token, rotación de llaves, datos personales en logs, límites de abuso, usuarios de la base de datos, escaneo de secretos, alertas y configuración de Docker.

## Decisión

### Encabezados HTTP
| Encabezado | API y panel | Invitación (hosting estático) |
|---|---|---|
| `Content-Security-Policy` | `default-src 'self'`; scripts y estilos solo `'self'`; `frame-ancestors 'none'`; `base-uri 'none'`; `form-action 'self'` | Restrictiva: `connect-src` solo la API; fuentes solo Google Fonts; el script inline autorizado por hash. `style-src` necesita `'unsafe-inline'` porque el diseño usa atributos `style`. `frame-ancestors 'none'` si el hosting permite encabezados |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` (cuando el dominio sea definitivo) | Igual, si el hosting lo permite |
| `X-Content-Type-Options` | `nosniff` | `nosniff` |
| `Referrer-Policy` | `no-referrer` | `no-referrer` |

En la invitación, lo que el hosting no pueda enviar como encabezado se declara con `<meta>` (CSP sin `frame-ancestors`, `referrer`). Es un cambio de I-5 sujeto a su aprobación.

### Tokens
- **Hash:** HMAC-SHA-256 del token con una llave secreta (`TOKEN_HASH_KEY`). Para 128 bits aleatorios no hace falta un hash lento.
- **Copia cifrada:** cifrado autenticado (AES-256-GCM, con nonce aleatorio de 96 bits por registro). Cada registro guarda el identificador de la llave que lo cifró.
- **Rotación de llaves:**
  1. Se agrega la llave nueva como actual, conservando la anterior.
  2. Un comando de mantenimiento descifra cada copia, la vuelve a cifrar con la llave actual y recalcula el HMAC si cambió la llave de hash.
  3. Cuando el comando termina sin errores, se retira la llave anterior.
  - Los enlaces enviados siguen funcionando durante todo el proceso.

### Datos personales en logs y errores
- **Regla general:** ningún log, mensaje de error ni respuesta de error contiene tokens, nombres, teléfonos, alergias, mensajes ni notas. Los logs usan una lista cerrada de campos permitidos (ruta sin parámetros, código de estado, duración, código INV cuando aplique, identificador de petición).
- **Sin servicios externos de rastreo de errores** (ningún SaaS de errores ni de analítica).

### Abuso
- **Rate limiting por token (estricto)** y **por IP (generoso**, porque las redes móviles comparten IP). Valores iniciales configurables: por token, 20 consultas y 10 respuestas por hora; por IP, 300 peticiones por hora. Se guardan en memoria; basta con una sola instancia.
- **Tamaño máximo de cuerpo:** API pública 4 KB; API del panel 64 KB; archivo de importación 2 MB.

### Base de datos
- **Dos usuarios:**
  - Uno de **migraciones** (dueño del esquema), usado solo por el comando `migrate`.
  - Uno de **ejecución**, solo con lectura y escritura de datos, sin permisos de esquema. La tarea de borrado usa el de ejecución.
- **TLS obligatorio** hacia la DB, con verificación de certificado cuando el proveedor lo permita.
- Se mantiene: Postgres privado, sin acceso público. Se reevalúa solo al elegir proveedor (ADR 0004).

### Secretos
- **Escaneo de secretos antes de cada commit** con un hook local (la herramienta se aprueba en I-1). El repositorio es público.

### Alertas e informes
- Si `purge` o `backup` fallan, se envía una **alerta** al canal que se defina.
- Cada ejecución genera un **informe de conteos** (filas afectadas por tipo, sin datos personales).
- El canal de alertas está **pendiente**.

### Docker
- Imagen base **fijada por digest**.
- Proceso con **usuario no root**.
- `HEALTHCHECK` contra el endpoint de salud.
- **Apagado ordenado:** atiende SIGTERM, termina las peticiones en curso y cierra conexiones dentro del tiempo de gracia.

## Consecuencias

- Las rutas de fuga más comunes (logs, errores, encabezados ausentes, secretos en el repo) quedan cerradas por diseño.
- La rotación de llaves es posible sin reenviar enlaces.
- Las cifras de rate limiting son iniciales y se ajustan con las pruebas.

## Pendientes

- Canal de alertas.
- Herramienta de escaneo de secretos (se propone en I-1).
