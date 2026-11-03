# 5. Reglas de negocio

Catálogo de reglas aceptadas. Garantía: **DB**, **API** o **Ambas**; la interfaz nunca es garantía. Si no hay ADR de origen, se indica **sugerencia**.

## A. Invitación y pases

| # | Regla | Garantía | ADR |
|---|---|---|---|
| A1 | Cada invitación (familia o grupo) tiene nombre a mostrar, código INV único no secreto y como máximo un enlace activo | Ambas | 0006, 0008 |
| A2 | Pases = adultos + niños autorizados; mínimo 1 adulto | Ambas | 0006 |
| A3 | Los infantes son informativos: no suman pases ni entran en la respuesta | Ambas | 0006 |
| A4 | Solo los novios modifican adultos, niños, infantes, nombre, categorías, mesa, nota y teléfonos | API | 0005, 0006 |
| A5 | No se pueden bajar los pases por debajo de los confirmados en la respuesta vigente | Ambas | 0006 |
| A6 | Lado, grupo y rol son catálogos cerrados e internos; el invitado no los ve | Ambas | 0006 |
| A7 | La mesa es opcional y solo se ve en el panel | API | 0006 |
| A8 | Teléfono principal y contacto alterno normalizados a +52; nunca se le piden al invitado | API | 0006 |
| A9 | No hay personas individuales; un niño autorizado concreto se identifica en la nota interna | — (modelo) | 0006 |

## B. Respuesta del invitado

| # | Regla | Garantía | ADR |
|---|---|---|---|
| B1 | Una sola respuesta vigente por invitación | DB | 0007 |
| B2 | Si asiste: total entre 1 y los pases. Si no asiste: 0. Sin desglose entre adultos y niños | Ambas | 0007 |
| B3 | El invitado no escribe nombres, no aumenta pases y no agrega niños; la API pública no tiene esos campos | API | 0006, 0007 |
| B4 | Alergias (una por invitación) y mensaje son opcionales y tienen longitud máxima | Ambas | 0007 |
| B5 | Todo texto del invitado o del Excel se trata como texto, nunca como HTML (invitación, panel, exportación) | API + frontends | 0010 |
| B6 | Cambios ilimitados dentro del plazo; cada cambio crea una versión inmutable con fecha y origen | Ambas | 0007 |
| B7 | Cualquiera con el enlace puede responder; no hay código adicional | API | 0008 |
| B8 | Los novios pueden registrar una respuesta en nombre del invitado; origen = admin y el actor queda registrado | Ambas | 0007 |
| B9 | Si dos dispositivos envían cambios, gana el último y ambos quedan en el historial | API | **sugerencia** |

## C. Plazo, bloqueo y estados

| # | Regla | Garantía | ADR |
|---|---|---|---|
| C1 | Fecha límite configurable; inicial: 6 feb 2027 23:59, −06:00 | API (configuración) | 0007 |
| C2 | Vencido el plazo, el invitado no crea ni cambia respuestas (`409 plazo_cerrado`) | API | 0007 |
| C3 | Los novios desbloquean una invitación concreta con su propia fecha de vencimiento | API | 0007 |
| C4 | Sin token, con token inválido o con plazo vencido, la invitación se ve completa y solo cambia la sección RSVP. Con plazo vencido y respuesta, se muestra la respuesta | Frontend + API | 0011 |
| C5 | Las fechas que se muestran salen de la configuración, no de texto fijo | Frontend + API | 0011 |
| C6 | Al congelar el RSVP antes del borrado no se aceptan cambios del invitado ni desbloqueos; el panel queda en solo lectura + exportación | API | **sugerencia aceptada** (desarrolla el "congelar RSVP" de 0010; ocurre antes del 5 abr 2027) |

## D. Enlaces y tokens

| # | Regla | Garantía | ADR |
|---|---|---|---|
| D1 | Enlace `https://[dominio]/#t=<token>`; 128 bits aleatorios en base64url; uno por invitación | API | 0013 |
| D2 | La invitación lee el token del fragmento, lo guarda solo durante la visita, lo quita de la barra y lo envía en el cuerpo de la petición | Frontend | 0013 |
| D3 | Se guardan el hash (para buscar) y una copia cifrada (para reenviar); la llave vive en una variable de entorno | Ambas | 0008 |
| D4 | Revocar o regenerar invalida el token anterior al instante | Ambas | 0008 |
| D5 | No se genera enlace para invitaciones en revisión | API | 0009 |
| D6 | Las respuestas públicas no exponen IDs internos ni el código INV | API | 0008 |
| D7 | La API nunca registra el token (ni en logs ni en errores) | API | 0008, 0013 |
| D8 | Rate limiting en lookup y response | API | 0008 |
| D9 | Token inexistente y token revocado reciben la misma respuesta (`404 enlace_no_valido`) | API | **sugerencia** (coherente con 0011, mensaje b) |
| D10 | La vista previa de WhatsApp es genérica, sin nombres | Frontend estático | 0008 |

## E. Panel, roles, importación y exportación

| # | Regla | Garantía | ADR |
|---|---|---|---|
| E1 | Login con Google restringido a listas de correos; novios = total, planner = lectura + exportación | API | 0005 |
| E2 | Cookies `Secure`/`HttpOnly`/`SameSite` y CSRF en toda operación que modifica datos | API | 0005 |
| E3 | Solo los novios importan | API | 0005, 0009 |
| E4 | Importación repetible: con código existente se actualiza, sin código se da de alta, con código desconocido es error | API | 0009 |
| E5 | Las invitaciones que no vienen en el archivo no se borran; se reportan | API | 0009 |
| E6 | "# Pases" solo valida; si no coincide con adultos + niños, la fila entra marcada "requiere revisión" | API | 0009 |
| E7 | Comentario → nota interna; si no hay columna Rol, también rol. La columna Rol manda sobre Comentario | API | 0009 |
| E8 | Al reimportar se leen Grupo y Rol; se ignoran ¿Asistirá?, Pases confirmados, Mensaje y Alergias | API | 0009 |
| E9 | Exportación: Código INV + 14 columnas de la planner + Mensaje, Grupo, Rol, Alergias; con protección contra fórmulas | API | 0009 |
| E10 | Recordatorios manuales: lista de pendientes + mensaje o enlace `wa.me` | Panel + API | 0003 |
| E11 | Se auditan importaciones, exportaciones, desbloqueos, enlaces y ediciones del admin | Ambas | 0005, 0009 |
| E12 | Importar primero genera una vista previa y luego se aplica en una sola transacción | API | **sugerencia aceptada** |
| E13 | Si una reimportación marca para revisión una invitación con enlace activo, el enlace sigue funcionando y el panel solo avisa. No se puede generar ni regenerar el enlace hasta corregirla | API | **sugerencia aceptada** (complementa 0009) |
| E14 | La planner no ve, copia ni gestiona enlaces, no prepara mensajes de WhatsApp y no ve la auditoría | API | **sugerencia aceptada** (interpreta "solo lectura" de 0005) |

## F. Datos personales y retención

| # | Regla | Garantía | ADR |
|---|---|---|---|
| F1 | Ningún dato real en el repo, código, seeds, pruebas, documentación ni commits | Proceso | 0010 |
| F2 | Antes del 5 abr 2027: congelar, exportar, respaldo final | Proceso | 0010 |
| F3 | 5 abr 2027: se borran teléfonos y alergias, también del historial | Tarea programada + DB | 0010 |
| F4 | 4 jun 2027: se borra el resto de los datos personales | Tarea programada + DB | 0010 |
| F5 | Cada respaldo vence en la fecha de borrado del dato más restrictivo que contenga | Proceso + almacenamiento | 0010 |
| F6 | La exportación final descargada se borra o se recorta (sin teléfonos ni alergias) el 5 abr 2027 | Proceso | 0010 |
| F7 | Después del borrado final se apagan la API y la DB | Proceso | 0010 |
| F8 | Si se restaura un respaldo, la tarea de borrado se ejecuta antes de reabrir el servicio | Proceso | **sugerencia aceptada** |
