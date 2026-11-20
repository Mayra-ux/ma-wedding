# ADR 0027 — Congelamiento por rol

- **Estado:** Aceptado
- **Fecha:** 2026-11-20
- **Reemplaza parcialmente:** ADR 0016 (fecha y alcance del congelamiento, respuestas del admin, novios sin congelamiento), ADR 0017 (restaurar archivadas "antes del congelamiento") y ADR 0024 (texto del estado «congelada»)
- **Complementa:** ADR 0025 (la fecha límite no cambia) y ADR 0026 (privilegios de la planner)

## Contexto

El ADR 0016 congelaba el RSVP para todos el domingo 7 de marzo de 2027, incluidos los novios. Los novios decidieron que el congelamiento aplique por rol: a los invitados un mes antes de la boda, a la planner hasta el día de la boda, y a ellos nunca.

## Decisión

| Rol | Cierre (configurable por migración) | Desde entonces |
|---|---|---|
| Invitados | **Sábado 6 de febrero de 2027, 00:00 (−06:00)** (`congelamiento`) | No confirman ni modifican nada, **aunque tengan un desbloqueo vigente** |
| Planner | **Sábado 6 de marzo de 2027 incluido**; cierre `2027-03-07T00:00:00-06:00` (`cierre_planner`) | Solo lectura total; ya no marca recordatorios |
| Novios | **Ninguno** | Registran respuestas, editan todos los campos (incluidos adultos, niños y pases), archivan, restauran y gestionan enlaces en cualquier momento, con auditoría |

- **La fecha límite de los invitados no cambia:** sábado 30 de enero de 2027 incluido; el plazo cierra cuando `ahora ≥ 2027-01-31T00:00-06:00` (ADR 0025).
- **Desbloqueo:** solo después del cierre del plazo, y su vencimiento nunca supera el congelamiento. La ventana real va **del 31 de enero al 5 de febrero de 2027**: el 6 de febrero a las 00:00 ya está congelado. Pedir un desbloqueo después del congelamiento responde `409 rsvp_congelado`; retirarlo se permite siempre.
- **Las fechas de borrado no cambian** (5 abr y 4 jun 2027, ADR 0010).
- **Invitación pública:** el estado «congelada» usa el mismo texto que «cerrada» (con o sin respuesta), que invita a escribir al chat de WhatsApp, en lugar de «Gracias por ser parte de nuestra leyenda. La confirmación de asistencia ya está cerrada.»
- **Base de datos:** la migración 0005 cambia `congelamiento` y agrega `cierre_planner`, con `congelamiento ≤ cierre_planner` y `cierre_planner` anterior a la primera fecha de borrado.

## Consecuencias

- Los novios pueden atender cambios de último momento hasta el día de la boda y después, siempre con auditoría.
- La planner tiene un mes más que los invitados para enviar recordatorios del evento.
- Como los datos pueden cambiar después del congelamiento, la exportación final y el respaldo final se hacen justo antes del primer borrado (5 abr 2027).
