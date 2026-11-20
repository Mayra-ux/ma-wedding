# 7. Contratos conceptuales de la API

Contratos conceptuales, sin implementación. Las rutas son orientativas, van bajo `/api/v1` y todas las respuestas son JSON salvo las exportaciones. El panel compilado se sirve en `/admin/` desde la misma API (ADR 0015).

Forma común de error:

```
{ "error": { "code": "<codigo_estable>", "message": "<texto para mostrar>", "fields": { "<campo>": "<motivo>" } } }
```

`fields` solo aparece en errores de validación. Ningún error incluye el token, datos personales ni trazas (ADR 0019).

---

## 7.1 API pública (invitación)

Sin cookies ni sesión; el token va en el cuerpo (ADR 0013). `Cache-Control: no-store`. CORS solo para el origen de la invitación, sin credenciales. Cuerpo máximo de 4 KB. Rate limiting por token y por IP.

### Consultar invitación

| | |
|---|---|
| **Recurso / método** | `POST /api/v1/public/invitation/lookup` |
| **Entrada** | `token` |
| **Salida 200** | `nombre_mostrar`, `pases`, `fecha_limite` (la global: **instante exacto del cierre**, ISO 8601 con zona, p. ej. `2027-01-31T00:00:00-06:00`), `fecha_limite_mostrar` (último día local para responder, `AAAA-MM-DD`, p. ej. `2027-01-30`; la invitación lo presenta como «sábado 30 de enero de 2027» sin calcularlo; ADR 0025), `estado` (`abierta`, `cerrada` o `congelada`), `abierta_hasta` (cierre del plazo o del desbloqueo vigente; nulo si no está abierta), `respuesta` (nula u objeto con `asiste`, `confirmados`, `alergias`, `mensaje`, `actualizada`) |
| **Errores** | `400 solicitud_invalida` · `404 enlace_no_valido` (inexistente, revocado o archivada) · `413 cuerpo_demasiado_grande` · `429 demasiadas_solicitudes` |

No devuelve el código INV, IDs, categorías, mesa, teléfonos ni nota.

### Guardar respuesta

| | |
|---|---|
| **Recurso / método** | `POST /api/v1/public/invitation/response` |
| **Entrada** | `token`, `asiste`, `confirmados`, `alergias` (opcional, máx. 200), `mensaje` (opcional, máx. 500) |
| **Salida 200** | La `respuesta` registrada. Si `asiste` es falso, las alergias quedan vacías (ADR 0017) |
| **Errores** | `400` · `404 enlace_no_valido` · `409 plazo_cerrado` (cerrada sin desbloqueo, o congelada) · `422 confirmados_fuera_de_rango` · `422 validacion` · `413` · `429` |

Efecto: en una transacción crea una versión nueva y la marca como vigente (ADR 0007).

### Implementación (fase I-4)

- **Entrada estricta:** tipos estrictos (`asiste` booleano, `confirmados` entero) y sin campos de más; un campo no previsto (p. ej. `pases`) → `400 solicitud_invalida`. El token solo viaja en el cuerpo; no existen variantes en la URL.
- **Orden de las comprobaciones** (lo que no depende del token se responde antes de buscarlo, para no revelar si existe): límite por IP (`429`) → cuerpo > 4 KB (`413`) → JSON, tipos o campos (`400`) → longitudes y caracteres (`422 validacion`, con `fields`) → límite por token (`429`) → token no válido por cualquier motivo, incluido el formato (`404 enlace_no_valido`, cuerpo idéntico) → plazo (`409 plazo_cerrado`) → rango (`422 confirmados_fuera_de_rango`).
- **Textos libres:** `
` → `
`; espacios al inicio y al final se quitan; vacío → `null`. Se rechazan caracteres de control (categoría Unicode Cc) salvo salto de línea y tabulador (`fields`: `caracteres_no_permitidos`); longitud en caracteres (`demasiado_largo`).
- **`asiste=false`:** exige `confirmados=0` (si no, `422 confirmados_fuera_de_rango`); las alergias se vacían sin error y el mensaje se conserva (ADR 0017).
- **Concurrencia:** la búsqueda del token toma `SELECT … FOR UPDATE` sobre la invitación; plazo, desbloqueo y pases se leen bajo el bloqueo.
- **CORS:** solo en `/api/v1/public`; `Access-Control-Allow-Origin` = `INVITATION_ORIGIN`, método `POST`, encabezado `Content-Type`, sin credenciales, `max-age` 600.
- **Encabezados en toda respuesta de la API:** `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'`, `X-Request-ID`; `Strict-Transport-Security` solo con `SECURITY_HSTS=true` (dominio definitivo). Sin encabezado `server`.

### Mensajes (provisionales hasta aprobar los textos de I-5)

| `code` | `message` |
|---|---|
| `solicitud_invalida` | La solicitud no es válida. |
| `enlace_no_valido` | Este enlace no es válido. |
| `plazo_cerrado` | El plazo para confirmar ya cerró. |
| `confirmados_fuera_de_rango` | El número de asistentes no es válido. |
| `validacion` | Revisa los datos enviados. |
| `cuerpo_demasiado_grande` | La solicitud es demasiado grande. |
| `demasiadas_solicitudes` | Demasiados intentos. Intenta de nuevo más tarde. (con `Retry-After`) |
| `error_interno` | Ocurrió un error. Intenta de nuevo. (500, sin traza) |

---

## 7.2 API del panel

Mismo origen que el panel; cookie de sesión. `X-CSRF-Token` en toda escritura. Cuerpo máximo de 64 KB (importación: 2 MB). Las invitaciones se identifican por su **código INV**.

Errores comunes: `401 no_autenticado` · `403 sin_permiso` · `403 csrf_invalido` · `404 no_encontrado` · `409 rsvp_congelado` (cualquier escritura de respuestas, desbloqueos o edición tras el congelamiento) · `422 validacion` · `429`.

Rol: **N** = novios, **P** = planner.

### Sesión

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `GET /api/v1/auth/google/login` | — | — | Redirección a Google + cookie temporal de OAuth | `503 auth_no_configurada` |
| `GET /api/v1/auth/google/callback` | — | `code`, `state` | Cookie + redirección a `/admin/` | `400 estado_invalido` · `403 correo_no_autorizado` · `403 identidad_no_verificada` · `502 proveedor_no_disponible` · `503 auth_no_configurada` |
| `GET /api/v1/auth/me` | N, P | — | `correo`, `rol` (`admin` o `lector`), `csrf_token` | — |
| `POST /api/v1/auth/logout` | N, P | — (`X-CSRF-Token`) | 204 y borra la cookie | — |

Los errores de `login` y `callback` son **páginas HTML** con textos fijos, porque los ve el navegador al volver de Google; nunca muestran el correo ni valores recibidos. Si la persona cancela en Google (`error` en el callback), vuelve a `/admin/` sin sesión. Implementación: fase I-6 (ADR 0005, notas de implementación).

### Invitaciones

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `GET /api/v1/admin/invitations` | N, P | `incluir_archivadas` (opcional) | **Lista completa sin paginar**: código, nombre, pases, adultos, niños, infantes, lado, grupo, roles, mesa, teléfonos, estado de respuesta, confirmados, alergias, en revisión, enlace activo/enviado. **Para N** incluye el mensaje; **para P**, no. El panel filtra y calcula estadísticas y recordatorios en el navegador | — |
| `GET /api/v1/admin/invitations/{codigo}` | N, P | — | Detalle + respuesta vigente (sin mensaje para P) | — |
| `POST /api/v1/admin/invitations` | N | Nombre, adultos, niños, infantes, lado, grupo, roles, mesa, nota, teléfonos | 201 con el código INV | `422 validacion` |
| `PATCH /api/v1/admin/invitations/{codigo}` | N | Campos a cambiar | Invitación actualizada; la marca de revisión se recalcula | `409 pases_menores_que_confirmados` |
| `POST /api/v1/admin/invitations/{codigo}/archive` | N | — | Archivada; enlace revocado | `409 ya_archivada` |
| `POST /api/v1/admin/invitations/{codigo}/restore` | N | — | Activa, sin enlace | `409 no_archivada` |
| `POST /api/v1/admin/invitations/{codigo}/unlock` | N | `hasta` | `desbloqueada_hasta` | `409 plazo_aun_abierto` · `422 mas_alla_del_congelamiento` |
| `DELETE /api/v1/admin/invitations/{codigo}/unlock` | N | — | Sin desbloqueo | — |

### Respuestas e historial

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `GET /api/v1/admin/invitations/{codigo}/history` | N, P | — | Versiones (sin mensaje para P) | — |
| `PUT /api/v1/admin/invitations/{codigo}/response` | N | `asiste`, `confirmados`, `alergias`, `mensaje` | Nueva versión vigente, origen admin; se permite después del plazo y hasta el congelamiento | `422 confirmados_fuera_de_rango` |

### Enlaces

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `GET /api/v1/admin/invitations/{codigo}/link` | N | — | Enlace `https://[dominio]/#t=<token>`, fecha de creación, estado de envío | `404 sin_enlace_activo` |
| `POST /api/v1/admin/invitations/{codigo}/link` | N | — | 201 enlace nuevo | `409 requiere_revision` · `409 archivada` · `409 ya_tiene_enlace` |
| `POST /api/v1/admin/invitations/{codigo}/link/regenerate` | N | — | 201 enlace nuevo; anterior revocado; marca de enviado reiniciada | `409 requiere_revision` · `409 archivada` |
| `POST /api/v1/admin/invitations/{codigo}/link/revoke` | N | — | Sin enlace activo | `404 sin_enlace_activo` |
| `POST /api/v1/admin/invitations/{codigo}/link/sent` | N | `origen` (`whatsapp` o `manual`) | Marca de enviado con fecha | `404 sin_enlace_activo` |

El botón de WhatsApp del panel arma el texto (plantilla de los novios, pendiente) y el enlace `wa.me` con el teléfono principal o el del contacto alterno, y llama a `link/sent` con `origen = whatsapp`.

### Importación y exportación

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `POST /api/v1/admin/imports/preview` | N | Archivo xlsx o csv | Resultado por fila (alta, actualización, error, revisión, avisos de duplicado y de teléfono faltante). **No guarda nada** | `415 formato_no_soportado` · `422 columnas_faltantes` · `413` |
| `POST /api/v1/admin/imports/apply` | N | El mismo archivo | Resumen aplicado + invitaciones del sistema que no venían en el archivo; un evento de auditoría con los conteos | Los mismos de preview |
| `POST /api/v1/admin/exports` | N, P | `formato` | Archivo: 19 columnas para N, 18 (sin Mensaje) para P; sin archivadas; con protección contra fórmulas | — |

### Configuración y auditoría

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `GET /api/v1/admin/config` | N, P | — | Cierre del plazo, congelamiento, fechas de borrado | — |
| `PATCH /api/v1/admin/config` | N | `cierre_plazo`, `congelamiento` | Configuración actualizada | `422 fecha_invalida` (el congelamiento debe ser posterior al cierre) |
| `GET /api/v1/admin/audit` | N | — | Eventos (lista completa) | — |

Las fechas de borrado se muestran pero no se editan desde el panel: son una decisión del ADR 0010.

### Salud

| Recurso / método | Uso | Salida |
|---|---|---|
| `GET /health` | `HEALTHCHECK` de Docker y del hosting | 200 si la API responde y la DB está accesible; no expone datos |

---

## 7.3 Códigos de error estables

| Código | HTTP | Lo usa | Qué muestra la interfaz |
|---|---|---|---|
| `solicitud_invalida` | 400 | Pública | Error genérico con opción de reintentar |
| `enlace_no_valido` | 404 | Pública | Mensaje (b) |
| `plazo_cerrado` | 409 | Pública | Mensaje (c) o la respuesta registrada |
| `rsvp_congelado` | 409 | Panel | Sistema congelado; solo lectura |
| `confirmados_fuera_de_rango` | 422 | Ambas | Corrige el stepper |
| `validacion` | 422 | Ambas | Mensaje por campo |
| `cuerpo_demasiado_grande` | 413 | Ambas | Archivo o texto demasiado grande |
| `demasiadas_solicitudes` | 429 | Ambas | Espera (texto pendiente para la invitación) |
| `no_autenticado` / `sin_permiso` / `csrf_invalido` | 401 / 403 | Panel | Volver a iniciar sesión o acceso denegado |
| `requiere_revision` / `archivada` | 409 | Panel | Corregir o restaurar antes de generar el enlace |
| `plazo_aun_abierto` / `mas_alla_del_congelamiento` | 409 / 422 | Panel | Límites del desbloqueo |
| `pases_menores_que_confirmados` | 409 | Panel | Ajustar la respuesta antes de bajar los pases |
