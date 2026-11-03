# ADR 0007 — Respuesta, plazo e historial

- **Estado:** Reemplazado parcialmente por ADR 0016
- **Fecha:** 2026-11-02

> Nota: el instante de cierre, los límites del desbloqueo, las respuestas del admin y el congelamiento quedan definidos por el ADR 0016. El resto de este ADR sigue vigente.

## Contexto

El formulario RSVP de la invitación hoy está simulado. Los novios necesitan números cerrados para el salón, pero también flexibilidad para casos puntuales y trazabilidad de los cambios.

## Decisión

### Respuesta
- **Una sola respuesta vigente por invitación** (garantizado en la base de datos).
- Si asiste: un **total** entre 1 y los pases asignados. Si no asiste: 0. No se desglosa entre adultos y niños; el banquete se planea con lo que el admin autorizó.
- El invitado no escribe nombres.
- Campos opcionales, con longitud máxima y tratados siempre como texto, nunca como HTML:
  - **Alergias o restricciones**, uno por invitación.
  - **Mensaje para los novios**, que ya existe en el diseño.
- Los novios pueden **registrar una respuesta en nombre del invitado** (por ejemplo, si confirma por teléfono); queda marcada con ese origen.

### Plazo
- **Fecha límite configurable.** Valor inicial: **sábado 6 de febrero de 2027 a las 23:59, hora del centro de México (−06:00)**.
- Al vencer, el invitado ya no puede crear ni cambiar respuestas.
- Los novios pueden **desbloquear una invitación concreta**, con una **fecha de vencimiento propia** para ese desbloqueo.

### Cambios e historial
- Cambios **ilimitados** mientras el plazo esté abierto.
- Cada versión de la respuesta se guarda en un **historial inmutable**, con fecha y origen (invitado o admin). La respuesta vigente es la última.
- El historial sigue las reglas de borrado del ADR 0010, incluida la purga de alergias el 5 abr 2027.

### Validación
- Toda regla se valida en el servidor; la interfaz solo ayuda.
- Hay límite de peticiones por token y por IP.

## Consecuencias

- Los números se cierran el 6 feb 2027, y las excepciones quedan acotadas y auditadas.
- El historial permite resolver dudas ("yo había confirmado 3").
- Mostrar la fecha y los mensajes en la invitación depende del ADR 0011.
