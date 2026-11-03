# 5. Reglas de negocio

Catálogo de reglas aceptadas. Garantía: **DB**, **API** o **Ambas**; la interfaz nunca es garantía. "Sugerencia aceptada" indica que la propuso el diseño y Mayra la aprobó.

## A. Invitación y pases

| # | Regla | Garantía | ADR |
|---|---|---|---|
| A1 | Cada invitación (familia o grupo) tiene nombre a mostrar, código INV único no secreto y como máximo un enlace activo | Ambas | 0006, 0008 |
| A2 | Pases = adultos + niños autorizados; mínimo 1 adulto | Ambas | 0006 |
| A3 | Los infantes son informativos: no suman pases ni entran en la respuesta | Ambas | 0006 |
| A4 | Solo los novios modifican adultos, niños, infantes, nombre, categorías, mesa, nota y teléfonos | API | 0005, 0006 |
| A5 | No se pueden bajar los pases por debajo de los confirmados en la respuesta vigente | Ambas | 0006 |
| A6 | Lado (Novia, Novio, Ambos) y grupo (Familia, Amigos, Trabajo, Otro) son catálogos cerrados, uno por invitación, internos | Ambas | 0006, 0017 |
| A7 | Rol en la boda: cero, uno o varios por invitación, del catálogo cerrado de 13 valores (ADR 0017) | Ambas | 0017 |
| A8 | La mesa es opcional y solo se ve en el panel | API | 0006 |
| A9 | Teléfono principal y contacto alterno normalizados a +52; nunca se le piden al invitado. Se permiten invitaciones sin teléfono, con aviso en el panel | API | 0006, 0017 |
| A10 | No hay personas individuales; un niño autorizado concreto se identifica en la nota interna | — (modelo) | 0006 |
| A11 | Longitudes máximas: nombre 120, mensaje 500, alergias 200, nota 500 | Ambas | 0017 |
| A12 | Las invitaciones no se borran: se archivan (enlace revocado, fuera de conteos y exportaciones) y se purgan el 4 jun 2027 | Ambas | 0017 |

## B. Respuesta del invitado

| # | Regla | Garantía | ADR |
|---|---|---|---|
| B1 | Una sola respuesta vigente por invitación | DB | 0007 |
| B2 | Si asiste: total entre 1 y los pases. Si no asiste: 0. Sin desglose entre adultos y niños | Ambas | 0007 |
| B3 | El invitado no escribe nombres, no aumenta pases y no agrega niños; la API pública no tiene esos campos | API | 0006, 0007 |
| B4 | Alergias (una por invitación) y mensaje son opcionales, con las longitudes de A11 | Ambas | 0007, 0017 |
| B5 | Si no asiste, se vacían las alergias y se conserva el mensaje | API | 0017 |
| B6 | Todo texto del invitado o del Excel se trata como texto, nunca como HTML (invitación, panel, exportación) | API + frontends | 0010 |
| B7 | Cambios ilimitados mientras esté abierta; cada cambio crea una versión inmutable con fecha y origen | Ambas | 0007 |
| B8 | Cualquiera con el enlace puede responder; no hay código adicional | API | 0008 |
| B9 | Si dos dispositivos envían cambios, gana el último y ambos quedan en el historial | API | Sugerencia (no se objetó) |

## C. Plazo, desbloqueo y congelamiento

| # | Regla | Garantía | ADR |
|---|---|---|---|
| C1 | Fecha límite configurable. El plazo está cerrado cuando `ahora ≥ 2027-02-07T00:00-06:00`; se presenta como "sábado 6 de febrero de 2027" | API (configuración) | 0007, 0016 |
| C2 | Con el plazo cerrado, el invitado no crea ni cambia respuestas (`409 plazo_cerrado`), salvo desbloqueo vigente | API | 0007, 0016 |
| C3 | El desbloqueo solo se permite después del plazo, y su vencimiento nunca supera el congelamiento | API | 0016 |
| C4 | Los novios pueden registrar respuestas después del plazo y hasta el congelamiento, con auditoría y origen = admin | Ambas | 0016 |
| C5 | Congelamiento: domingo 7 mar 2027 00:00 (−06:00), configurable. Desde ese instante nadie crea, cambia ni desbloquea respuestas; el panel queda en solo lectura + exportación | API | 0016 |
| C6 | Estados RSVP: abierta, sin token, enlace no válido, cerrada (con/sin respuesta), congelada (con/sin respuesta). La invitación siempre se ve completa | Frontend + API | 0011, 0016 |
| C7 | El mensaje (c) muestra siempre la fecha límite global, tomada de la configuración | Frontend + API | 0016 |

## D. Enlaces y tokens

| # | Regla | Garantía | ADR |
|---|---|---|---|
| D1 | Enlace `https://[dominio]/#t=<token>`; 128 bits aleatorios en base64url; uno por invitación | API | 0013 |
| D2 | La invitación lee el token del fragmento, lo guarda solo durante la visita, lo quita de la barra y lo envía en el cuerpo | Frontend | 0013 |
| D3 | Se guardan el HMAC-SHA-256 del token (búsqueda) y una copia con cifrado autenticado AES-256-GCM (reenvío), con identificador de llave | Ambas | 0008, 0019 |
| D4 | Las llaves se rotan con un comando que vuelve a cifrar y recalcula los hashes, sin invalidar enlaces | API (comando) | 0019 |
| D5 | Revocar, regenerar o archivar invalida el token anterior al instante | Ambas | 0008, 0017 |
| D6 | No se genera ni se regenera enlace para invitaciones en revisión | API | 0009 |
| D7 | Si una reimportación marca para revisión una invitación con enlace activo, el enlace sigue funcionando y el panel solo avisa | API | Sugerencia aceptada |
| D8 | Las respuestas públicas no exponen IDs internos ni el código INV | API | 0008 |
| D9 | Token inexistente, revocado o de invitación archivada reciben la misma respuesta (`404 enlace_no_valido`) | API | 0016 |
| D10 | Rate limiting por token (estricto) y por IP (generoso) | API | 0007, 0019 |
| D11 | La vista previa de WhatsApp es genérica, sin nombres | Frontend estático | 0008 |
| D12 | El enlace se marca como enviado automáticamente al usar el botón de WhatsApp, o manualmente. Regenerar reinicia la marca | API | 0017 |

## E. Panel, roles, importación y exportación

| # | Regla | Garantía | ADR |
|---|---|---|---|
| E1 | Login con Google restringido a listas de correos; novios = total, planner = lectura + exportación | API | 0005 |
| E2 | El panel lo sirve la API (mismo origen, enrutado por hash); cookie `Secure`/`HttpOnly`/`SameSite=Strict` y CSRF en toda escritura | API | 0005, 0015 |
| E3 | La planner ve alergias pero no los mensajes del invitado; no ve ni gestiona enlaces, no usa WhatsApp, no ve la auditoría | API | 0017 |
| E4 | Solo los novios importan | API | 0005, 0009 |
| E5 | Importación sin estado: vista previa (no guarda nada) y aplicación (se vuelve a subir el archivo, una transacción). Solo se audita el resumen | API | 0018 |
| E6 | Con código existente se actualiza, sin código se da de alta, con código desconocido es error de fila. Lo que no viene en el archivo no se borra | API | 0009 |
| E7 | Formatos: Infante = número; ¿Asistirá? = Sí/No/vacío; Pases confirmados vacío si pendiente; Invitado de = Novia/Novio/Ambos; Rol separado por `;` | API | 0018 |
| E8 | "# Pases" del Excel solo valida y se guarda como original. Si no coincide con adultos + niños → "requiere revisión"; la marca se quita sola al corregir | API | 0009, 0018 |
| E9 | Rol: la columna Rol manda. Sin ella, Comentario es rol solo si coincide exactamente con el catálogo; si no, es nota | API | 0018 |
| E10 | Al reimportar se leen Grupo y Rol; se ignoran ¿Asistirá?, Pases confirmados, Mensaje y Alergias | API | 0009 |
| E11 | Los duplicados por nombre solo generan aviso | API | 0018 |
| E12 | Exportación de los novios: Código INV + 14 columnas + Mensaje, Grupo, Rol, Alergias. Exportación de la planner: igual, sin Mensaje. "# Pases" calculado. Sin archivadas. Con protección contra fórmulas | API | 0009, 0018 |
| E13 | Recordatorios: invitaciones con enlace enviado y sin respuesta; WhatsApp al teléfono principal o al contacto alterno | Panel + API | 0003, 0017 |
| E14 | Se auditan importaciones, exportaciones, desbloqueos, enlaces, archivados, respuestas del admin y ediciones | Ambas | 0005, 0016 |

## F. Datos personales, retención y seguridad operativa

| # | Regla | Garantía | ADR |
|---|---|---|---|
| F1 | Ningún dato real en el repo, código, seeds, pruebas, documentación ni commits; escaneo de secretos antes de cada commit | Proceso | 0010, 0019 |
| F2 | Ningún log, error ni respuesta de error contiene tokens ni datos personales; los logs usan una lista cerrada de campos | API | 0019 |
| F3 | Sin servicios externos de rastreo de errores ni analítica | Proceso | 0019 |
| F4 | Antes del 5 abr 2027 (ya con el RSVP congelado el 7 mar): exportación final y respaldo final | Proceso | 0010, 0016 |
| F5 | 5 abr 2027: se borran teléfonos y alergias, también del historial | Tarea programada + DB | 0010 |
| F6 | 4 jun 2027: se borra el resto de los datos personales, incluidas las invitaciones archivadas | Tarea programada + DB | 0010, 0017 |
| F7 | Cada respaldo vence en la fecha de borrado del dato más restrictivo que contenga | Proceso + almacenamiento | 0010 |
| F8 | La exportación final descargada se borra o se recorta (sin teléfonos ni alergias) el 5 abr 2027 | Proceso | 0010 |
| F9 | Si se restaura un respaldo, la tarea de borrado se ejecuta antes de reabrir el servicio | Proceso | Sugerencia aceptada |
| F10 | Si `purge` o `backup` fallan, se emite una alerta; cada ejecución deja un informe de conteos sin datos personales | Tarea + proceso | 0019 |
| F11 | Dos usuarios de DB (migraciones / ejecución), TLS obligatorio, Postgres privado | Infraestructura | 0004, 0019 |
| F12 | Después del borrado final se apagan la API y la DB | Proceso | 0010 |
