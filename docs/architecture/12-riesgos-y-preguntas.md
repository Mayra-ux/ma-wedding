# 12. Riesgos y preguntas abiertas

## Riesgos

| # | Riesgo | Impacto | Mitigación | ADR |
|---|---|---|---|---|
| R1 | El invitado reenvía su enlace y un tercero responde | Respuesta incorrecta | Aceptado; historial + revocar o regenerar | 0008 |
| R2 | Una app o navegador pierde el fragmento `#t=` | El invitado ve el mensaje (a) | Probar con enlaces ficticios en WhatsApp iOS/Android antes de enviar (criterio de I-5) | 0013 |
| R3 | Marcador guardado sin el token | No puede responder desde el marcador | El mensaje (a) le indica usar su enlace | 0013 |
| R4 | Se pierde una llave de tokens | No se pueden reenviar los enlaces | Custodia fuera del proveedor; rotación con `rotate-keys`; en el peor caso, regenerar y reenviar | 0008, 0019 |
| R5 | Las exportaciones descargadas no se borran a tiempo | Teléfonos y alergias fuera de control tras el 5 abr | Auditoría de exportaciones; recordatorio; mención en el aviso de privacidad. La planner no recibe mensajes | 0010, 0018 |
| R6 | Un respaldo o una restauración reintroduce datos borrados | Incumple la retención | Vencimiento absoluto; `purge` después de restaurar | 0010 |
| R7 | Arranque en frío | Primera carga lenta del RSVP | Instancia persistente; no usar contenedores serverless | 0004 |
| R8 | Reimportación que marca para revisión una invitación con enlace enviado | — | Resuelto: el enlace sigue funcionando y el panel avisa (D7) | 0009 |
| R9 | SVG públicos con identificadores del sitio oficial del juego | Exposición del origen | Aceptado; usos cerrados por el ADR 0014 | 0012, 0014 |
| R10 | Logs o errores con tokens o datos personales | Fuga | Lista cerrada de campos; errores sin valores; sin rastreo externo | 0019 |
| R11 | Fechas mal interpretadas por la zona horaria | Plazo o congelamiento a deshora | Instantes con zona explícita (−06:00); el centro de México no tiene horario de verano desde 2022 | 0016 |
| R12 | Texto malicioso en el nombre, el mensaje o el Excel | Inyección | Siempre como texto; neutralizar fórmulas | 0009, 0010 |
| R13 | Root Directory de Vercel sin cambiar al hacer el merge de I-1 | El hosting publicaría la raíz (y con ella `api/` y `docs/`) | Cambiarlo junto con el merge; criterio explícito de I-1 | 0020 |
| R14 | `purge` o `backup` fallan en silencio | Incumplimiento de la retención o pérdida de datos | Alerta + informe de conteos | 0019 |
| R15 | Los límites por IP afectan a invitados detrás de la misma red móvil | Bloqueos falsos | Límite por IP generoso; el límite estricto es por token | 0019 |

## Preguntas abiertas

| # | Pregunta | Bloquea | ADR |
|---|---|---|---|
| ~~Q1~~ | **Cerrada:** la nota de adultos sí es del diseño aprobado (31 oct 2026); se insertó en `#vestimenta` y el emblema quedó cubierto por el ADR 0014 | — | 0011, 0014 |
| Q2 | Canal de contacto al que remite "escríbenos" | Textos (a), (b), (c) — I-5 | 0011 |
| Q3 | Texto del aviso de privacidad y responsable de los datos | Publicación del RSVP real — I-5/I-10 | 0010 |
| Q4 | Proveedor del PaaS y del Postgres administrado | Despliegue — I-10 | 0004 |
| Q5 | Dominio propio | URLs absolutas, HSTS, URI de redirección de OAuth definitiva, formato final del enlace — I-10. Ya no afecta a las cookies (ADR 0015) | 0002, 0013 |
| ~~Q6~~ | **Cerrada:** enlace activo + aviso en revisión (D7) | — | 0009 |
| Q7 | ¿La raíz de la invitación debe indexarse en buscadores? | Encabezados del hosting — I-10 | 0013 |
| ~~Q8~~ | **Cerrada:** catálogos de lado, grupo y rol definidos en el ADR 0017 | — | 0017 |
| Q9 | Plantilla del mensaje de WhatsApp | I-9 | 0003 |
| ~~Q10~~ | **Cerrada:** la planner no ve enlaces ni la auditoría, ni los mensajes del invitado | — | 0017 |
| ~~Q11~~ | **Cerrada:** congelamiento el domingo 7 mar 2027 00:00 (−06:00), configurable | — | 0016 |
| Q12 | Aprobación visual de I-5: alergias, aviso, estados, carga y error | I-5 | 0011 |
| Q13 | Texto del mensaje de rate limiting y del error de red | I-5 | 0011 |
| Q14 | Canal de alertas para `purge` y `backup` | I-10 | 0019 |
| Q15 | Herramientas de I-1: Python, PostgreSQL, gestor de paquetes, migraciones, escaneo de secretos | **Inicio de I-1** | 0019, 0020 |
| Q16 | Proyecto OAuth de Google (lo crea Mayra) | I-6 | 0005 |
| Q17 | Encabezados y un ejemplo **ficticio** del archivo de la planner (formato exacto, sin datos reales) | I-8 | 0018 |
