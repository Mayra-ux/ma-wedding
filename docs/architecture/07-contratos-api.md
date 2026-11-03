# 7. Contratos conceptuales de la API

Contratos conceptuales, sin implementación. Las rutas son orientativas y van versionadas bajo `/api/v1`. Todas las respuestas son JSON salvo las exportaciones. Los errores siguen una forma común:

```
{ "error": { "code": "<codigo_estable>", "message": "<texto para mostrar>", "fields": { "<campo>": "<motivo>" } } }
```

`fields` solo aparece en errores de validación. Ningún error incluye el token, datos personales ni trazas internas.

---

## 7.1 API pública (invitación)

Sin cookies ni sesión. La credencial es el token, que va en el cuerpo (ADR 0013). Todas las respuestas llevan `Cache-Control: no-store`. CORS solo admite el origen de la invitación.

### Consultar invitación

| | |
|---|---|
| **Recurso / método** | `POST /api/v1/public/invitation/lookup` (es `POST` para que el token no viaje en la URL) |
| **Quién** | La invitación, en nombre del invitado |
| **Entrada** | `token` |
| **Salida 200** | `nombre_mostrar`, `pases`, `fecha_limite` (ISO 8601 con zona), `estado` (`abierta` o `cerrada`), `abierta_hasta` (la fecha límite o la del desbloqueo, si aplica), `respuesta` (nula u objeto con `asiste`, `confirmados`, `alergias`, `mensaje` y `actualizada`) |
| **Errores** | `400 solicitud_invalida` (falta el token o el formato es incorrecto) · `404 enlace_no_valido` (inexistente o revocado, respuesta uniforme) · `429 demasiadas_solicitudes` |

No devuelve el código INV, IDs, categorías, mesa, teléfonos ni nota interna (ADR 0006, 0008).

### Guardar respuesta

| | |
|---|---|
| **Recurso / método** | `POST /api/v1/public/invitation/response` |
| **Quién** | La invitación, en nombre del invitado |
| **Entrada** | `token`, `asiste` (booleano), `confirmados` (entero), `alergias` (opcional), `mensaje` (opcional) |
| **Salida 200** | La `respuesta` registrada (misma forma que en lookup) |
| **Errores** | `400 solicitud_invalida` · `404 enlace_no_valido` · `409 plazo_cerrado` (vencido y sin desbloqueo, o RSVP congelado) · `422 confirmados_fuera_de_rango` (asiste con 0 o más que los pases, o no asiste con más de 0) · `422 validacion` (longitudes, tipos) · `429 demasiadas_solicitudes` |

Efecto: en una transacción crea una versión nueva del historial y reemplaza la respuesta vigente (ADR 0007).

---

## 7.2 API del panel

Requiere la cookie de sesión. Las operaciones que modifican datos requieren `X-CSRF-Token` ([06](06-autenticacion-autorizacion.md)). Errores comunes a todas: `401 no_autenticado` · `403 sin_permiso` · `403 csrf_invalido` · `404 no_encontrado` · `422 validacion` · `429 demasiadas_solicitudes`. En las rutas del panel, las invitaciones se identifican por su **código INV**, nunca por su ID interno.

Rol: **N** = novios, **P** = planner.

### Sesión

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `GET /api/v1/auth/google/login` | — | — | Redirección a Google | — |
| `GET /api/v1/auth/google/callback` | — | `code`, `state` (de Google) | Cookie de sesión + redirección al panel | `403 correo_no_autorizado` · `400 estado_invalido` |
| `GET /api/v1/auth/me` | N, P | — | `correo`, `rol`, `csrf_token` | — |
| `POST /api/v1/auth/logout` | N, P | — | 204 | — |

### Invitaciones

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `GET /api/v1/admin/invitations` | N, P | Filtros: lado, grupo, rol, estado de respuesta (pendiente / sí / no), en revisión, texto | Lista paginada: código, nombre, pases, adultos, niños, infantes, categorías, mesa, estado de respuesta, confirmados, en revisión. **N** ve teléfonos; **P** los ve también (los necesita en la exportación) | — |
| `GET /api/v1/admin/invitations/{codigo}` | N, P | — | Detalle completo + respuesta vigente + si tiene enlace activo | — |
| `POST /api/v1/admin/invitations` | N | Nombre, adultos, niños, infantes, lado, grupo, rol, mesa, nota, teléfonos | 201 con el código INV asignado | `422 validacion` (adultos < 1, catálogo inválido, teléfono inválido) |
| `PATCH /api/v1/admin/invitations/{codigo}` | N | Campos a cambiar | Invitación actualizada | `409 pases_menores_que_confirmados` |
| `DELETE /api/v1/admin/invitations/{codigo}` | N | — | 204; borra también su respuesta, historial y enlaces | **Sugerencia:** pide confirmación explícita en el panel |
| `POST /api/v1/admin/invitations/{codigo}/resolve-review` | N | — | Quita la marca de revisión si ya no hay inconsistencias | `409 sigue_inconsistente` |
| `POST /api/v1/admin/invitations/{codigo}/unlock` | N | `hasta` (fecha y hora futura) | `desbloqueada_hasta` | `422 fecha_invalida` · `409 rsvp_congelado` |
| `DELETE /api/v1/admin/invitations/{codigo}/unlock` | N | — | Quita el desbloqueo | — |

### Respuestas e historial

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `GET /api/v1/admin/invitations/{codigo}/history` | N, P | — | Versiones: número, asiste, confirmados, alergias, mensaje, origen, actor, fecha | — |
| `PUT /api/v1/admin/invitations/{codigo}/response` | N | `asiste`, `confirmados`, `alergias`, `mensaje` | Respuesta vigente (origen = admin) | `422 confirmados_fuera_de_rango` · `409 rsvp_congelado` |

Los novios pueden registrar una respuesta aunque el plazo haya vencido (ADR 0007 solo bloquea al invitado), salvo con el RSVP congelado.

### Enlaces y WhatsApp

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `GET /api/v1/admin/invitations/{codigo}/link` | N | — | Enlace completo `https://[dominio]/#t=<token>` (descifrado), fecha de creación | `404 sin_enlace_activo` |
| `POST /api/v1/admin/invitations/{codigo}/link` | N | — | 201 enlace nuevo | `409 requiere_revision` · `409 ya_tiene_enlace` |
| `POST /api/v1/admin/invitations/{codigo}/link/regenerate` | N | — | 201 enlace nuevo; el anterior queda revocado | `409 requiere_revision` |
| `POST /api/v1/admin/invitations/{codigo}/link/revoke` | N | — | 200 sin enlace activo | `404 sin_enlace_activo` |
| `GET /api/v1/admin/invitations/{codigo}/whatsapp-message` | N | — | `texto` (plantilla + enlace) y `wa_me_url` con el teléfono principal | `404 sin_enlace_activo` · `422 sin_telefono` |
| `GET /api/v1/admin/reminders` | N | — | Invitaciones con enlace y sin respuesta, cada una con su mensaje listo | — |

La plantilla del mensaje la definen los novios (pendiente); no se inventa.

### Importación y exportación

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `POST /api/v1/admin/imports` | N | Archivo xlsx o csv (tamaño máximo) | Lote en `vista_previa`: conteos + resultado por fila | `415 formato_no_soportado` · `422 columnas_faltantes` |
| `GET /api/v1/admin/imports/{lote}` | N | — | Detalle del lote y sus filas | — |
| `POST /api/v1/admin/imports/{lote}/apply` | N | — | Lote `aplicado` + invitaciones del sistema que no venían en el archivo | `409 lote_ya_aplicado` · `409 lote_obsoleto` (**sugerencia:** si los datos cambiaron desde la vista previa) |
| `POST /api/v1/admin/imports/{lote}/discard` | N | — | Lote `descartado` | — |
| `POST /api/v1/admin/exports` | N, P | `formato` (xlsx o csv) | Archivo con las columnas del ADR 0009 | — |

### Estadísticas, configuración y auditoría

| Recurso / método | Rol | Entrada | Salida | Errores propios |
|---|---|---|---|---|
| `GET /api/v1/admin/stats` | N, P | — | Totales: invitaciones, pases, adultos, niños, infantes; respondidas, pendientes, sí, no; confirmados; desglose por lado, grupo y rol | — |
| `GET /api/v1/admin/config` | N, P | — | Fecha límite, fechas de borrado, congelado | — |
| `PATCH /api/v1/admin/config` | N | `fecha_limite`, `rsvp_congelado` | Configuración actualizada | `422 fecha_invalida` |
| `GET /api/v1/admin/audit` | N | Filtros: acción, código, fecha | Eventos paginados | — |

Las fechas de borrado se muestran pero no se editan desde el panel (**sugerencia**): son una decisión del ADR 0010, no un ajuste operativo.

---

## 7.3 Códigos de error estables

| Código | HTTP | Lo usa | Qué muestra la interfaz |
|---|---|---|---|
| `solicitud_invalida` | 400 | Pública | Error genérico con opción de reintentar |
| `enlace_no_valido` | 404 | Pública | Mensaje (b) del ADR 0011 |
| `plazo_cerrado` | 409 | Pública | Mensaje (c) o la respuesta registrada |
| `confirmados_fuera_de_rango` | 422 | Pública, panel | Corrige el stepper (no debería pasar con la interfaz) |
| `validacion` | 422 | Ambas | Mensaje por campo |
| `demasiadas_solicitudes` | 429 | Ambas | "Intenta de nuevo en unos minutos" (texto pendiente) |
| `no_autenticado` / `sin_permiso` / `csrf_invalido` | 401 / 403 | Panel | Volver a iniciar sesión o acceso denegado |
| `requiere_revision` | 409 | Panel | Corregir la invitación antes de generar el enlace |
| `pases_menores_que_confirmados` | 409 | Panel | Ajustar la respuesta antes de bajar los pases |
| `rsvp_congelado` | 409 | Ambas | Sistema en cierre previo al borrado |
