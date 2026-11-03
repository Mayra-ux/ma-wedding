CLAUDE.md — Invitación digital M&A (boda de Mayra y Alejandro)

Contexto permanente del proyecto. Léelo completo antes de cualquier tarea. Idioma de trabajo: español (México). Código, nombres de variables y commits pueden ir en inglés.

1. Datos oficiales (NO modificar nunca)
Novios: Mayra y Alejandro · Monograma: M&A
Fecha: sábado 6 de marzo de 2027
Ceremonia religiosa: Templo San Francisco de Asís · 1:00 p. m. Maps: https://www.google.com/maps/place/Templo+San+Francisco+de+As%C3%ADs/@22.1492414,-100.9799864,17z/data=!3m2!4b1!5s0x842aa200f92953e3:0x5da576b56a6ddfff!4m6!3m5!1s0x842aa201021fcc9f:0x7d98890494befe79!8m2!3d22.1492365!4d-100.9774115!16s%2Fg%2F1tdmvyt0
Recepción: La Viña Jardín de Eventos · 4:00 p. m. Maps: https://www.google.com/maps/place/La+Vi%C3%B1a+Jard%C3%ADn+de+Eventos/@22.199253,-100.8952941,17z/data=!4m17!1m10!3m9!1s0x842aa12bfba8499d:0x7b935db99bfadd22!2sLa+Vi%C3%B1a+Jard%C3%ADn+de+Eventos!8m2!3d22.199253!4d-100.8952941!10e5!14m1!1BCgIgARICEAE!16s%2Fg%2F11hc_0g172!3m5!1s0x842aa12bfba8499d:0x7b935db99bfadd22!8m2!3d22.199253!4d-100.8952941!16s%2Fg%2F11hc_0g172
Mesa de regalos: Liverpool · número de evento 60001357
Evento exclusivo para adultos (no niños).
Colores reservados: verde esmeralda → damas · blanco/ivory/marfil/beige → novia · gris Oxford → caballeros del novio · color del novio → por definir · rojo → no permitido.

Datos aún pendientes (mostrar como placeholder entre corchetes, NUNCA inventar): formalidad del código de vestimenta, color del novio, fecha límite de RSVP, nombre del invitado/familia y lugares (vendrán del backend), momentos restantes del itinerario, fotografías profesionales.

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

Tokens de color (:root): marfil 
#FBF7EE · pergamino 
#F3EAD7 · papel 
#F7F0E1 · beige 
#E9DCC0 · esmeralda 
#0D4F3D · esmeralda-hondo 
#0A3A2E · bosque 
#08231C · musgo 
#5C7D6B · oro 
#D1AE66 · champagne 
#E9D6A6 · oro-viejo 
#B8964F · oro-texto 
#6B5222 · tinta 
#1E2A24 · tinta-2 
#34433B · tenue 
#5A645E. El verde 
#0D4F3D y el dorado 
#D1AE66 vienen del monograma oficial. (--hoja es un resto sin uso; se puede eliminar.)

Colores fuera de tokens, intencionales: muestras del código de vestimenta (esmeralda damas 
#046A4A, novia 
#FFFFFF/
#F8F1E1/
#EFE6D2/
#D9C7A5, gris Oxford 
#474A51, rojo tachado 
#C1121F) y tonos de texto sobre fondos esmeralda (
#E7DFCB, 
#D6CDB6). No los "normalices" a tokens.

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
Ornamentos (decidido por los novios, 2 nov 2026): se conservan los tres orn-*.svg actuales del paquete TotK, por decisión consciente de Mayra. Úsalos solo donde ya están: no agregues más piezas de ese paquete ni otros elementos oficiales del juego.
Los lugares "2" del RSVP son un valor de demostración, no un dato: se sustituirán por el dato de la API en la fase I-5.
No usar hojas ni ornamentos vegetales.
No usar fotos de stock ni generadas por IA. Las fotos de la sesión de pareja llegarán después; no prepares galería hasta que se pida.
Mobile first. Sin scroll horizontal. Accesible (labels, foco visible, contraste).
El monograma se usa tal cual: no redibujar, recolorear, deformar ni separar.
4. Arquitectura backend — estado de decisiones

Decidido:

Base de datos: PostgreSQL estándar (sin extensiones propietarias).
La invitación sigue sin framework (HTML + CSS + JS vanilla, sin build). No la migres a React ni a otro framework. La conexión con el backend se hace con JavaScript vanilla sobre el formulario existente.
Panel administrativo: opción preferida React + Vite como aplicación aparte, solo para administradores, sujeta a la decisión 16 (panel en el mismo servicio o separado).
Posible a futuro (no ahora): Vite sin framework para la invitación, solo si hace falta optimizar las fotos de la sesión o versionar los nombres de archivo. La página tendría que verse idéntica.

Recomendado, pendiente de aprobación explícita:

Alternativa A: frontend estático actual + API ligera en contenedor Docker + PostgreSQL. Panel admin privado.
Lenguaje de la API: FastAPI (Python) o Node/TypeScript → por decidir.

Sin decidir: hosting definitivo (VPS, PaaS, cloud, serverless de contenedores), dominio, proveedor de Postgres administrado.

Principios obligatorios:

Portabilidad: nada atado a un proveedor; configuración por variables de entorno; Docker como mecanismo de portabilidad.
Seguridad: tokens de invitación aleatorios ≥128 bits (guardar solo su hash si se aprueba), nunca IDs secuenciales públicos, toda validación en el servidor, rate limiting, admin con 2FA o login de Google restringido, cookies seguras + CSRF, DB no expuesta a internet, usuario de DB con privilegios mínimos, respaldos diarios cifrados fuera del proveedor.
Reglas ya claras: una sola respuesta vigente por invitación; lugares confirmados entre 1 y los asignados si asiste, 0 si no; el invitado nunca puede aumentar sus lugares; los lugares cuentan solo adultos.
La vista previa de WhatsApp no debe mostrar nombres de invitados.
Plan post-boda: congelar RSVP, exportar, respaldo final, borrar datos personales en fecha acordada, apagar API/DB.

Decisiones funcionales pendientes (no asumir): nombres por adulto o solo número; nombres de acompañantes; confirmación parcial; categorías (lado novia/novio); mesas; fecha límite y si bloquea; cambios de respuesta (cuántos, hasta cuándo); datos de contacto; recordatorios; restricciones alimenticias; administradores y roles; forma de envío de enlaces; formato del enlace; retención de datos; panel en el mismo servicio o separado.

5. Forma de trabajo
Trabajamos por fases. No avances a la siguiente fase sin autorización explícita de Mayra.
Antes de editar: explica qué vas a hacer, qué archivos tocarás y por qué. Espera confirmación en cambios grandes.
No inventes datos, reglas de negocio ni textos de la boda.
No instales dependencias, no crees bases de datos reales, no hagas commits ni push sin que se te pida.
Nunca escribas secretos en el repo; usa .env (ignorado) y .env.example con valores ficticios.
Si algo contradice este archivo, detente y pregunta.