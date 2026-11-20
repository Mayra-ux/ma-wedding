# ADR 0024 — Textos de la invitación, canal de contacto, aviso de privacidad y salida a producción de I-5

- **Estado:** Reemplazado parcialmente por ADR 0027
- **Fecha:** 2026-11-15
- **Reemplaza parcialmente:** ADR 0011 (textos de los mensajes a, b y c, que dependían del canal de contacto)
- **Complementa:** ADR 0010 (aviso de privacidad), ADR 0013, ADR 0016, ADR 0021 y ADR 0025

> Nota: el ADR 0027 reemplaza el texto del estado «Congelada»: ahora usa el mismo texto que «Cerrada» (con o sin respuesta). El resto de este ADR sigue vigente.

## Contexto

La fase I-5 conecta la invitación con la API pública. El ADR 0011 dejó pendientes los textos de los estados de la sección RSVP y el canal de contacto; el ADR 0010 dejó pendientes el texto del aviso de privacidad y el responsable de los datos. Además, unir la invitación conectada a `main` cambia lo que ve cualquier visitante del despliegue provisional.

## Decisión

### Canal de contacto
- El canal es **el mismo chat de WhatsApp donde cada invitado recibió su invitación**. No se publica ningún número en la página.

### Textos aprobados (se usan tal cual)
`[fecha]` se presenta en español como «sábado 30 de enero de 2027»; `[N]` es el número de lugares («1 lugar» en singular).

| Estado | Texto |
|---|---|
| Cargando | Abriendo tu invitación… |
| Sin token | Para confirmar tu asistencia, abre el enlace personal que te enviamos por WhatsApp. Si no lo encuentras, escríbenos a ese mismo chat y con gusto te lo reenviamos. |
| Enlace no válido | Este enlace ya no está activo. Escríbenos al chat de WhatsApp donde recibiste tu invitación y te enviaremos uno nuevo. |
| Error al cargar | No pudimos abrir tu invitación. Revisa tu conexión e inténtalo de nuevo. (botón REINTENTAR) |
| Fecha límite (columna izquierda) | Confirma a más tardar el [fecha] |
| Abierta con respuesta (sobre el formulario precargado) | Ya registramos tu respuesta: [N] lugares. Puedes modificarla hasta el [fecha]. · Si no asiste: Ya registramos que no podrás acompañarnos. Si cambian tus planes, puedes modificarlo hasta el [fecha]. |
| Cerrada sin respuesta | El periodo de confirmación terminó el [fecha]. Si necesitas confirmar o hacer algún cambio, escríbenos al chat de WhatsApp donde recibiste tu invitación y lo revisamos con gusto. |
| Cerrada con respuesta | Tu respuesta quedó registrada: [N] lugares. El periodo para modificarla terminó el [fecha]; si necesitas algún cambio, escríbenos al chat de WhatsApp. · Si no asiste: Tu respuesta quedó registrada: no podrás acompañarnos. (mismo final) |
| Congelada | Gracias por ser parte de nuestra leyenda. La confirmación de asistencia ya está cerrada. |
| Enviando | El botón muestra ENVIANDO… |
| Éxito | Se conservan los textos del bloque de confirmación del diseño aprobado. |
| Error al guardar | No pudimos guardar tu respuesta. Revisa tu conexión e inténtalo de nuevo. |
| Demasiados intentos (429) | Hiciste varios intentos seguidos. Espera unos minutos e inténtalo de nuevo. |

- En los estados cerrada y cerrada con respuesta, `[fecha]` es siempre la **fecha límite global** (regla C7).
- **Campo de alergias:** etiqueta «ALERGIAS O RESTRICCIONES ALIMENTICIAS (OPCIONAL)», placeholder «Ej. vegetariano, alergia a nueces…», nota «Solo la usaremos para preparar el banquete.» Se oculta si el invitado elige «No podré».
- **Bajo el botón de envío:** «Usaremos tus datos solo para organizar nuestra boda.» con el enlace «Aviso de privacidad».

### Aviso de privacidad
- Bloque desplegable (`<details>`) al final de la sección «¿Te unes a la aventura?», con el texto aprobado por los novios (responsables, datos que se usan, finalidad, con quién se comparten, plazos de conservación, derechos y cambios).
- Los responsables son Mayra y Alejandro; sus **apellidos están pendientes** y se muestran como `[APELLIDOS]` hasta que los proporcionen.

### Salida a producción de la invitación conectada
- I-5 se une **solo a `develop`**. No se une a `main` (que publica Vercel) hasta que se cumplan **todas** estas condiciones:
  1. La API está desplegada (fase I-10) y `api-base` y la CSP de la invitación apuntan a ella.
  2. Los apellidos del aviso de privacidad están resueltos.
  3. La prueba con un enlace ficticio abierto desde WhatsApp en iOS y Android pasó.
- Se mantiene el ADR 0021: ningún enlace real se envía hasta definir el dominio definitivo.

## Consecuencias

- Mientras I-5 no esté en `main`, el despliegue provisional sigue mostrando la versión anterior de la sección.
- El aviso de privacidad bloquea la salida a producción hasta tener los apellidos (ADR 0010).
- Cambiar un texto de esta tabla es un cambio de decisión y requiere un ADR nuevo.
