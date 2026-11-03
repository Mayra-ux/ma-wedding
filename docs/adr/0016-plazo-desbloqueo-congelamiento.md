# ADR 0016 — Plazo, desbloqueo y congelamiento del RSVP

- **Estado:** Aceptado
- **Fecha:** 2026-11-02
- **Reemplaza parcialmente:** ADR 0007 (instante de cierre, reglas del desbloqueo, respuestas del admin) y ADR 0011 (tabla de estados y fecha del mensaje c)

## Contexto

La validación de la Fase 3 encontró varios puntos ambiguos: el instante exacto del cierre, qué fecha muestra el mensaje (c), los límites del desbloqueo, si el admin puede registrar respuestas después del plazo y cómo se llama el estado posterior al congelamiento. El ADR 0011 no contemplaba ese estado.

## Decisión

### Fechas (configurables)
| Hito | Valor inicial | Regla |
|---|---|---|
| Cierre del plazo | 2027-02-07T00:00-06:00 | El plazo está **cerrado cuando `ahora ≥ 2027-02-07T00:00-06:00`**. Para el invitado se presenta como "sábado 6 de febrero de 2027" |
| Congelamiento del RSVP | **Domingo 7 de marzo de 2027, 00:00 (−06:00)** | Desde ese instante nadie (ni invitados ni novios) crea, cambia ni desbloquea respuestas; el panel queda en solo lectura + exportación |

### Desbloqueo
- Solo se permite **después del cierre del plazo**.
- Su fecha de vencimiento **nunca puede ser posterior al congelamiento**.

### Respuestas registradas por el admin
- Los novios pueden registrar o cambiar una respuesta en nombre del invitado **después del plazo y hasta el congelamiento**, con auditoría y con origen = admin en el historial.

### Estados de la sección RSVP (sustituye la tabla del ADR 0011)

| Estado | Condición | Sección RSVP |
|---|---|---|
| Abierta | Token válido, antes del cierre o con desbloqueo vigente | Formulario, con la respuesta vigente precargada si existe |
| Sin token | No hay `#t=` ni token en la sesión | Mensaje (a) |
| Enlace no válido | Token inexistente, revocado o de invitación archivada | Mensaje (b) |
| Cerrada sin respuesta | Token válido, plazo cerrado, sin desbloqueo, antes del congelamiento | Mensaje (c) |
| Cerrada con respuesta | Ídem, con respuesta | La respuesta registrada, sin opción de modificarla |
| **Congelada** sin respuesta | Token válido, después del congelamiento | Mensaje (c) |
| **Congelada** con respuesta | Ídem, con respuesta | La respuesta registrada, sin opción de modificarla |

- Para el invitado, "congelada" se ve igual que "cerrada". La distinción existe para la API y el panel.
- El mensaje (c) muestra **siempre la fecha límite global**, aunque la invitación haya tenido un desbloqueo ya vencido.
- Se mantienen del ADR 0011: la invitación se ve completa, los textos (a)/(b)/(c) siguen pendientes de aprobación y del canal de contacto, y la fecha sale de la configuración.

## Consecuencias

- Las reglas de tiempo quedan sin ambigüedad y se pueden probar con un reloj simulado.
- Entre el 7 feb y el 7 mar los novios todavía pueden ajustar respuestas, por ejemplo cuando un invitado avisa por teléfono.
- El borrado del 5 abr y del 4 jun (ADR 0010) ocurre con el sistema ya congelado.
