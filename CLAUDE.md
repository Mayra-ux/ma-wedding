CLAUDE.md — Invitación digital M&A (boda de Mayra y Alejandro)

Contexto permanente del proyecto. Léelo completo antes de cualquier tarea. Idioma de trabajo: español (México). Código, nombres de variables y commits pueden ir en inglés.

1. Datos oficiales (NO modificar nunca)
Novios: Mayra y Alejandro · Monograma: M&A
Fecha: sábado 6 de marzo de 2027
Ceremonia religiosa: Templo San Francisco de Asís · 1:00 p. m. Maps: https://www.google.com/maps/place/Templo+San+Francisco+de+As%C3%ADs/@22.1492414,-100.9799864,17z/data=!3m2!4b1!5s0x842aa200f92953e3:0x5da576b56a6ddfff!4m6!3m5!1s0x842aa201021fcc9f:0x7d98890494befe79!8m2!3d22.1492365!4d-100.9774115!16s%2Fg%2F1tdmvyt0
Recepción: La Viña Jardín de Eventos · 4:00 p. m. Maps: https://www.google.com/maps/place/La+Vi%C3%B1a+Jard%C3%ADn+de+Eventos/@22.199253,-100.8952941,17z/data=!4m17!1m10!3m9!1s0x842aa12bfba8499d:0x7b935db99bfadd22!2sLa+Vi%C3%B1a+Jard%C3%ADn+de+Eventos!8m2!3d22.199253!4d-100.8952941!10e5!14m1!1BCgIgARICEAE!16s%2Fg%2F11hc_0g172!3m5!1s0x842aa12bfba8499d:0x7b935db99bfadd22!8m2!3d22.199253!4d-100.8952941!16s%2Fg%2F11hc_0g172
Mesa de regalos: Liverpool · número de evento 60001357
Fecha límite de confirmación (RSVP): sábado 6 de febrero de 2027, 23:59, hora del centro de México (−06:00); configurable.
Evento para adultos. Los novios pueden autorizar niños por invitación como excepción (ver §4). La nota de "evento exclusivo para adultos" de la invitación no cambia.
Colores reservados: verde esmeralda → damas · blanco/ivory/marfil/beige → novia · gris Oxford → caballeros del novio · color del novio → por definir · rojo → no permitido.

Datos aún pendientes (mostrar como placeholder entre corchetes, NUNCA inventar): formalidad del código de vestimenta, color del novio, nombre del invitado/familia y lugares (vendrán del backend), momentos restantes del itinerario, fotografías profesionales.

2. Estado actual del proyecto
Repo: Mayra-ux/ma-wedding. Ramas: main (publicada) y develop (trabajo; Mayra la sube al remoto).
La ciudad (San Luis Potosí) se deduce de las coordenadas de Maps, pero no es un dato que los novios hayan pedido mostrar: no la agregues a la invitación.
Despliegue PROVISIONAL en Vercel como sitio estático desde la raíz. Vercel no es el hosting definitivo.
Mayra se encarga de repositorio, ramas, merges y despliegues. Tú no haces push, no despliegas y no creas servicios ni bases de datos reales.

Archivos:

index.html — página completa (HTML + CSS + JS vanilla, sin framework ni build).
mono-espada.webp (monograma con espada: portada y cierre) · mono.webp (sin espada: nav, favicon).
orn-meandro.svg, orn-espirales.svg, orn-anillo.svg — ornamentos tomados del paquete "Zelda TotK Vector Bundle" que entregaron los novios. Ese paquete deriva de arte del sitio oficial del juego (los SVG traen IDs como Zelda_Bundle). Se conservan por decisión de los novios (ver §3, "Ornamentos").
og.jpg — vista previa para WhatsApp (1200×630).
vercel.json — solo cleanUrls y caché. No usar funciones propietarias de Vercel.
3. Diseño APROBADO — congelado

El diseño visual está aprobado. No cambies colores, tipografías, composición, textos, animaciones, fondos, orden de secciones ni el monograma salvo petición explícita. Si una tarea de backend requiere tocar index.html, el cambio debe ser mínimo y quirúrgico (p. ej. reemplazar un placeholder por un dato que llega de la API) y debes listar exactamente qué líneas cambias antes de hacerlo.

Tokens de color (:root): marfil #FBF7EE · pergamino #F3EAD7 · papel #F7F0E1 · beige #E9DCC0 · esmeralda #0D4F3D · esmeralda-hondo #0A3A2E · bosque #08231C · musgo #5C7D6B · oro #D1AE66 · champagne #E9D6A6 · oro-viejo #B8964F · oro-texto #6B5222 · tinta #1E2A24 · tinta-2 #34433B · tenue #5A645E. El verde #0D4F3D y el dorado #D1AE66 vienen del monograma oficial.

Colores fuera de tokens, intencionales: muestras del código de vestimenta (esmeralda damas #046A4A, novia #FFFFFF/#F8F1E1/#EFE6D2/#D9C7A5, gris Oxford #474A51, rojo tachado #C1121F) y tonos de texto sobre fondos esmeralda (#E7DFCB, #D6CDB6). No los "normalices" a tokens.

Tipografías (Google Fonts): Cinzel (títulos, etiquetas) · Cormorant Garamond (texto) · Pinyon Script (acentos de 1–2 frases).

Estructura de secciones (en este orden):

Nav fija (monograma + capítulos; en móvil muestra el capítulo activo) y barra de progreso dorada.
I · Portada — arco/portal, anillo giratorio, monograma con espada con destello enmascarado, "Mayra & Alejandro", 06 · 03 · 2027, "Toda leyenda comienza con una promesa.", botón "COMENZAR LA AVENTURA".
Franja de runas (glifos geométricos propios, en verde).
II · Nuestra aventura comienza — capitular "É", "Es peligroso ir solo… acompáñanos."
III · El gran día — escena esmeralda, cuenta regresiva en vivo (2027-03-06T13:00-06:00), calendario de marzo 2027 con el 6 marcado, botón a Google Calendar.
El camino — tarjetas en arco: IV Ceremonia (esmeralda) y V Recepción (marfil), botones "CÓMO LLEGAR".
La travesía · Itinerario — línea de tiempo; solo Ceremonia 1:00 p. m. y Recepción 4:00 p. m. son datos reales; el resto son placeholders punteados.
VI · Código de vestimenta — "[ FORMALIDAD POR CONFIRMAR ]", tarjetas de colores (esmeralda, novia, novio por definir, gris Oxford, rojo tachado con "COLOR NO PERMITIDO") y nota cálida de evento para adultos.
Un presente · Mesa de regalos — Liverpool, número 60001357, botón copiar, botón a mesaderegalos.liverpool.com.mx.
VII · ¿Te unes a la aventura? — formulario RSVP (hoy SIMULADO: no guarda nada).
VIII · Cierre — monograma con espada, "Gracias por ser parte de nuestra leyenda".

Recursos de ambiente: textura de papel (SVG noise), escenas con doble marco y esquinas ornamentales, ornamentos SVG con parallax, partículas doradas en canvas, aparición suave por scroll (contenido siempre visible en reposo). Todo respeta prefers-reduced-motion.

Reglas visuales permanentes:

Sin rojo en todo el diseño, salvo el círculo rojo tachado del código de vestimenta.
No usar marcas ni arte oficial de Nintendo: Trifuerza, logotipos de Zelda, escudo hyliano, símbolos de los Sabios, alfabeto zonai, íconos del juego. La temática se evoca con ornamentos propios, la espada del monograma y el lenguaje de leyenda.
Ornamentos (decidido por los novios, 2 nov 2026; ADR 0012 y ADR 0014): se conservan los tres orn-*.svg actuales del paquete TotK, por decisión consciente de Mayra. Usos permitidos, exactamente los del diseño aprobado: ornamentos de fondo con parallax en Portada (meandro, espirales), Aventura (anillo), El gran día (espirales), El camino (meandro, anillo), Itinerario (espirales), Vestimenta (meandro), Mesa de regalos (anillo), Confirmar (espirales) y Cierre (anillo, espirales), más el emblema de orn-anillo.svg en la nota de adultos de Vestimenta. No agregues más piezas de ese paquete ni otros elementos oficiales del juego, y no uses estas tres en lugares nuevos.
Los lugares "2" del RSVP son un valor de demostración, no un dato: se sustituirán por el dato de la API en la fase I-5.
No usar hojas ni ornamentos vegetales.
No usar fotos de stock ni generadas por IA. Las fotos de la sesión de pareja llegarán después; no prepares galería hasta que se pida.
Mobile first. Sin scroll horizontal. Accesible (labels, foco visible, contraste).
El monograma se usa tal cual: no redibujar, recolorear, deformar ni separar.
4. Arquitectura backend — estado de decisiones

Decidido (detalle y justificación en docs/adr/):

Arquitectura: Alternativa A, aprobada. Invitación estática actual + API en contenedor Docker + PostgreSQL estándar (sin extensiones propietarias).
API: FastAPI (Python).
Invitación: sigue sin framework (HTML + CSS + JS vanilla, sin build). No la migres a React ni a otro framework. La conexión con el backend se hace con JavaScript vanilla sobre el formulario existente.
Panel administrativo: aplicación aparte con React + Vite, solo para administradores.
Acceso al panel: login con Google restringido a listas de correos en variables de entorno. Roles: novios = admin total; planner = solo lectura + exportación.
Operación: PaaS de contenedores + Postgres administrado.
Dominio: propio.
Galería futura: solo fotos de la sesión de pareja.
Posible a futuro (no ahora): Vite sin framework para la invitación, solo si hace falta optimizar las fotos o versionar los nombres de archivo. La página tendría que verse idéntica.

Sin decidir: proveedor del PaaS y del Postgres administrado, compra del dominio, canal de contacto para los mensajes del RSVP.

Principios obligatorios:

Portabilidad: nada atado a un proveedor; configuración por variables de entorno; Docker como mecanismo de portabilidad.
Seguridad: tokens de invitación aleatorios ≥128 bits (guardar su hash para buscarlo y una copia cifrada con llave en variable de entorno para reenviarlo; un token por invitación), nunca IDs secuenciales públicos, toda validación en el servidor, rate limiting, admin con 2FA o login de Google restringido, cookies seguras + CSRF, DB no expuesta a internet, usuario de DB con privilegios mínimos, respaldos diarios cifrados fuera del proveedor.
Reglas ya claras: una sola respuesta vigente por invitación; lugares confirmados entre 1 y los asignados si asiste, 0 si no; el invitado nunca puede aumentar sus lugares.
Niños: el evento es para adultos, CON excepciones decididas por los novios. Solo el admin puede autorizar niños en una invitación (cuántos y, si aplica, quiénes). El invitado nunca puede agregar niños. La nota de "evento exclusivo para adultos" de la invitación no cambia. El formato de la planner distingue: infante (<2 años, sin asiento ni alimentos) y niño (con asiento y alimentos).
Acompañantes: una invitación puede incluir personas con nombre y lugares de acompañante sin nombre (pase adicional). Los novios asignan esos pases; el invitado no los aumenta.
Teléfono: se guarda el teléfono principal (y opcionalmente un contacto alterno) para generar el mensaje de WhatsApp desde el panel. No se le pide al invitado.
Rol en la boda (padrinos, damas, pajes, etc.): campo interno de la invitación/persona. El invitado no lo ve.
Importación y exportación: el panel importa la lista en el formato Excel/CSV de la planner, validando inconsistencias (ej. # Pases ≠ adultos + niños), y exporta con esas mismas columnas: No., Nombre Invitado, # Pases, Teléfono, Contacto alterno, Tel. contacto alterno, Infante, Adultos, # Niños, Invitado de, ¿Asistirá?, Pases confirmados, # de mesa, Comentario.

Datos reales de invitados — regla estricta: el repositorio es público. El Excel de la lista vive FUERA del repo (C:\Users\mayoa\OneDrive\Documentos\Repositorios\). No lo abras, no lo copies al repo y no pongas nombres ni teléfonos reales en código, pruebas, seeds, documentación ni commits. Los datos de desarrollo son siempre ficticios. *.xlsx y *.csv deben estar en .gitignore.

La vista previa de WhatsApp no debe mostrar nombres de invitados.
Plan post-boda: congelar RSVP, exportar, respaldo final, borrar datos personales en fecha acordada, apagar API/DB.

Decisiones funcionales (detalle en docs/adr/):

Invitación = familia o grupo, con nombre a mostrar, código interno no secreto (INV-###) y un token. Pases = adultos + niños autorizados; los infantes son informativos y no cuentan. Sin personas individuales en la v1: si hace falta identificar a un niño autorizado, va en la nota interna.
El invitado confirma solo un total (1..pases si asiste, 0 si no). No escribe nombres. Campos opcionales: alergias (uno por invitación) y mensaje.
Fecha límite configurable, inicialmente sábado 6 feb 2027 a las 23:59 hora del centro de México (−06:00); al vencer se bloquea. Los novios pueden desbloquear una invitación con vencimiento propio. Cambios ilimitados dentro del plazo, con historial.
Sin token, token inválido o plazo vencido: la invitación se ve completa y solo se reemplaza la sección RSVP (textos pendientes de aprobación visual en I-5).
Importación repetible del Excel de la planner con código INV como llave; al reimportar se leen Grupo y Rol (la columna Rol manda sobre Comentario) y se ignoran ¿Asistirá?, Pases confirmados, Mensaje y Alergias. Exportación: Código INV + columnas de la planner + Mensaje del invitado, Grupo, Rol, Alergias.
Recordatorios y envío de enlaces: manuales por WhatsApp desde el panel.
Retención: alergias y teléfonos se borran el 5 abr 2027 (también en el historial); el resto de datos personales el 4 jun 2027. Los respaldos vencen en esas mismas fechas. La exportación final descargada contiene teléfonos y alergias: ese archivo se borra o se reemplaza por una versión sin esas columnas el 5 abr 2027.

Pendientes (no asumir): canal de contacto, texto del aviso de privacidad y responsable de los datos, aprobación visual de I-5 (alergias, aviso, estados), proveedor de hosting, dominio.

5. Forma de trabajo
Trabajamos por fases. No avances a la siguiente fase sin autorización explícita de Mayra.
Antes de editar: explica qué vas a hacer, qué archivos tocarás y por qué. Espera confirmación en cambios grandes.
No inventes datos, reglas de negocio ni textos de la boda.
No instales dependencias, no crees bases de datos reales, no hagas commits ni push sin que se te pida.
Nunca escribas secretos en el repo; usa .env (ignorado) y .env.example con valores ficticios.
Si algo contradice este archivo, detente y pregunta.