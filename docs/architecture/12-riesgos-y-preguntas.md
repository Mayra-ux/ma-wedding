# 12. Riesgos y preguntas abiertas

## Riesgos

| # | Riesgo | Impacto | Mitigación | ADR |
|---|---|---|---|---|
| R1 | El invitado reenvía su enlace y un tercero responde | Respuesta incorrecta | Aceptado por los novios; el historial deja rastro y el admin puede revocar o regenerar | 0008 |
| R2 | Una app o navegador pierde el fragmento `#t=` al abrir el enlace | El invitado ve el mensaje (a) en lugar del formulario | Probar con enlaces de prueba en WhatsApp iOS y Android y en navegadores móviles antes de enviar | 0013 |
| R3 | El invitado guarda un marcador sin el token (tras `replaceState`) | No puede responder desde el marcador | El mensaje (a) le indica que use su enlace personal | 0013 |
| R4 | Se pierde la llave de cifrado de tokens | No se pueden reenviar los enlaces existentes | Guardarla fuera del proveedor; si se pierde, regenerar y reenviar todos | 0008 |
| R5 | Las exportaciones descargadas no se borran a tiempo | Teléfonos y alergias fuera de control después del 5 abr | Auditoría de exportaciones; recordatorio a novios y planner; mención en el aviso de privacidad | 0010 |
| R6 | Un respaldo o una restauración reintroduce datos borrados | Incumple la retención | Vencimiento por fecha absoluta; ejecutar `purge` después de cualquier restauración | 0010 |
| R7 | Arranque en frío del hosting | La primera carga del RSVP tarda | Mantener una instancia activa o evitar contenedores serverless | 0004 |
| R8 | Una fila reimportada marca para revisión una invitación que **ya** tiene enlace enviado | El invitado podría quedarse sin poder responder | Resuelto: el enlace sigue funcionando y el panel solo avisa (regla E13, aceptada) | 0009 |
| R9 | Los SVG públicos llevan identificadores del sitio oficial del juego | Exposición del origen del arte | Aceptado por los novios | 0012 |
| R10 | Los logs del hosting o de la API capturan el cuerpo de las peticiones | Exposición del token | La API filtra el campo del token; no activar registro de cuerpos en el hosting | 0008, 0013 |
| R11 | Fallan los cambios de horario o de zona horaria | Plazo que cierra a deshora | Guardar fechas con zona horaria explícita (−06:00); el centro de México no tiene horario de verano desde 2022 | 0007 |
| R12 | Texto malicioso en el nombre, el mensaje o el Excel | Inyección en el panel o en Excel | Siempre como texto; neutralizar fórmulas en la exportación | 0009, 0010 |

## Preguntas abiertas

| # | Pregunta | Bloquea | ADR |
|---|---|---|---|
| ~~Q1~~ | **Cerrada:** la nota de "evento exclusivo para adultos" sí forma parte del diseño aprobado el 31 oct 2026. El `index.html` del repositorio se había subido antes de ese cambio; CLAUDE.md y el ADR 0011 estaban bien. La nota se insertó en `#vestimenta`, y el uso de `orn-anillo.svg` como su emblema quedó cubierto por el ADR 0014 | — | 0011, 0014 |
| Q2 | Canal de contacto al que remite "escríbenos" | Aprobación de los textos (a), (b) y (c) | 0011 |
| Q3 | Texto del aviso de privacidad y responsable de los datos | Publicación del RSVP real | 0010 |
| Q4 | Proveedor del PaaS y del Postgres administrado | Despliegue real, respaldos | 0004 |
| Q5 | Dominio propio (y subdominios para panel y API, que afectan a las cookies `SameSite`) | URLs absolutas, CORS, cookies, formato final del enlace | 0002, 0013 |
| ~~Q6~~ | **Cerrada (aceptada):** si una invitación con enlace ya enviado queda en revisión al reimportar, el enlace sigue funcionando y el panel solo avisa (regla E13) | — | 0009 |
| Q7 | ¿La raíz de la invitación debe indexarse en buscadores? | Encabezados del hosting | 0013 |
| Q8 | Lista completa de valores del catálogo de roles (padrinos, damas, pajes… "etc.") y si grupo admite más valores | Catálogos e importación | 0006 |
| Q9 | Plantilla del mensaje de WhatsApp | Recordatorios y envío | 0003 |
| ~~Q10~~ | **Cerrada (aceptada):** la planner no ve enlaces ni la auditoría (regla E14) | — | 0005 |
| Q11 | Fecha exacta del congelamiento del RSVP. Ya está aceptado que ocurre antes del 5 abr 2027 y qué bloquea (regla C6) | Calendario post-boda | 0010 |
| Q12 | Aprobación visual de I-5: alergias, aviso, estados, carga y error | Integración de `index.html` | 0011 |
| Q13 | Texto del mensaje de rate limiting y del error de red | I-5 | 0011 |
