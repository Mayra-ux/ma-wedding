# ADR 0011 — Estados de la sección RSVP en la invitación

- **Estado:** Aceptado
- **Fecha:** 2026-11-02

## Contexto

La invitación pública se abre con o sin token, con tokens revocados y antes o después del plazo. El diseño está congelado y solo admite cambios mínimos aprobados.

## Decisión

- La invitación **siempre se muestra completa**. Solo la **sección RSVP (capítulo VII)** cambia según el estado:

| Estado | Sección RSVP |
|---|---|
| Token válido, plazo abierto (o invitación desbloqueada) | Formulario con nombre a mostrar, pases asignados y la respuesta vigente si existe |
| Sin token | Mensaje (a) |
| Token inválido o revocado | Mensaje (b) |
| Token válido, plazo vencido, sin respuesta | Mensaje (c) |
| Token válido, plazo vencido, con respuesta | La respuesta registrada, sin opción de modificarla |

- Textos propuestos por los novios, **pendientes de aprobación final**:
  - (a) "Para confirmar tu asistencia, usa el enlace personal que te enviamos. Si no lo encuentras, escríbenos y con gusto te lo reenviamos."
  - (b) "Este enlace ya no está activo. Escríbenos y te enviaremos tu enlace actualizado."
  - (c) "El periodo de confirmación terminó el sábado 6 de febrero de 2027. Si necesitas hacer algún cambio, escríbenos y con gusto lo revisamos."
- La fecha del mensaje (c) y la del aviso "Confirma antes del…" se toman de la configuración (ADR 0007), no de texto fijo.
- El nombre a mostrar y los pases provienen de la API y se insertan siempre como texto. El valor "2" actual es de demostración.
- Se retiran los avisos "Vista previa del diseño".
- La nota de "evento exclusivo para adultos" no cambia.

## Consecuencias

- Quien abre la invitación sin enlace personal ve toda la información del evento.
- Los cambios en `index.html` se limitan a la sección RSVP y al JavaScript que la controla.

## Pendientes

- **Canal de contacto** al que remite "escríbenos". Bloquea la aprobación de los textos (a), (b) y (c).
- **Aprobación visual de la fase I-5:** campo de alergias, línea de aviso de privacidad, mensajes de estado y presentación de la respuesta registrada. Ningún cambio visual se aplica sin esa aprobación.
- **Texto del aviso de privacidad** (ver ADR 0010).
