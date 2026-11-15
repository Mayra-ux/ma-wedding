# ADR 0025 — Nueva fecha límite del RSVP: sábado 30 de enero de 2027

- **Estado:** Aceptado
- **Fecha:** 2026-11-15
- **Reemplaza parcialmente:** ADR 0016 (valor inicial del cierre del plazo) y, por extensión, el valor inicial del ADR 0007

## Contexto

El ADR 0016 fijó el cierre del plazo en `2027-02-07T00:00-06:00` (último día para responder: sábado 6 de febrero de 2027). Al aprobar los textos de la invitación (fase I-5), los novios adelantaron la fecha límite para tener los números cerrados con más anticipación.

## Decisión

- **Último día para responder:** sábado 30 de enero de 2027, **incluido completo**, hora del centro de México (−06:00).
- **Cierre del plazo:** el plazo está cerrado cuando `ahora ≥ 2027-01-31T00:00:00-06:00`.
- **Presentación en la invitación:** "Confirma a más tardar el sábado 30 de enero de 2027". La API devuelve `fecha_limite = 2027-01-31T00:00:00-06:00` (instante exacto del cierre) y `fecha_limite_mostrar = 2027-01-30` (contrato 07).
- **No cambian:** el congelamiento (domingo 7 de marzo de 2027, 00:00, −06:00) ni las fechas de borrado (5 de abril y 4 de junio de 2027).
- Se aplica con la migración `0003`, porque el usuario de ejecución solo puede leer `configuracion_evento` (ADR 0019).
- Se mantiene del ADR 0016 todo lo demás: desbloqueo solo después del cierre y nunca más allá del congelamiento, respuestas del admin hasta el congelamiento, tabla de estados y uso de la fecha límite global en el mensaje de plazo cerrado.

## Consecuencias

- Entre el 31 de enero y el 7 de marzo de 2027 los novios pueden desbloquear invitaciones y registrar respuestas en nombre de los invitados (antes, desde el 7 de febrero).
- Los tests de cierre exacto se fijan en `2027-01-31T00:00:00-06:00` (un segundo antes: abierta; en el instante: cerrada).
