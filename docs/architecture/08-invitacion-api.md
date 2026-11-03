# 8. Comunicación invitación–API

Basado en ADR 0002, 0011 y 0013. Describe el cambio **previsto** para la fase I-5. **Nada de esto se aplica ahora**, y cualquier pieza visual nueva requiere la aprobación de I-5.

## 8.1 Principios

- La invitación sigue siendo un solo `index.html` vanilla, sin build ni dependencias (ADR 0002).
- Los cambios se limitan a la **sección VII (RSVP)** y al bloque de JavaScript que la controla. No se tocan colores, tipografías, composición ni las demás secciones (CLAUDE.md §3).
- **La página siempre se sirve en `/`.** El token va en el fragmento (`/#t=<token>`, ADR 0013), así que no hacen falta reglas de reescritura en ningún hosting y `vercel.json` no cambia.
- Todo dato de la API se inserta con `textContent`, nunca como HTML.

## 8.2 Lectura del token

Al cargar la página, antes de pintar la sección RSVP:

1. Si `location.hash` empieza con `#t=`, se toma el valor que sigue. Se valida que sea base64url y tenga la longitud esperada; si no, se trata como "sin token".
2. Se guarda en una variable en memoria y, con try/catch, en `sessionStorage`.
3. Se llama a `history.replaceState(null, '', location.pathname + location.search)` para quitar el fragmento sin agregar una entrada al historial.
4. Si no venía `#t=`, se intenta recuperar el token de `sessionStorage` (por ejemplo, tras recargar la pestaña).
5. Los demás fragmentos (`#aventura`, `#fecha`, `#confirmar`…) no se tocan, porque solo se procesa el prefijo `t=`.

Al navegar con el menú después de quitar el token, el fragmento cambia a `#aventura` y similares, pero el token sigue en memoria.

## 8.3 URL de la API

- Una sola constante de configuración en `index.html` (p. ej. una etiqueta `<meta name="api-base" content="https://api.[dominio]">`) con la URL base de la API.
- **Sugerencia:** usar la meta y no una variable dentro del script, para que cambiarla sea una edición de una línea al pasar del hosting provisional al definitivo.
- La API permite CORS solo desde el origen de la invitación.

## 8.4 Estados de la sección RSVP

| Estado | Cuándo | Qué se muestra (elementos existentes) | ¿Requiere aprobación de I-5? |
|---|---|---|---|
| Cargando | Mientras responde lookup | El bloque de RSVP con `aria-busy="true"` y el botón de envío deshabilitado. **Sugerencia:** sin spinner nuevo; se reutiliza el estilo actual | Sí, si se agrega cualquier indicador visual |
| Abierta sin respuesta | lookup 200, `abierta`, sin respuesta | `#rsvp-form`. Nombre en lugar de `[Nombre del invitado o familia]`, "N lugares" en lugar de "2 lugares", fecha límite en lugar de `[fecha límite por definir]`, stepper `1..pases` | No (sustituye placeholders) |
| Abierta con respuesta | lookup 200, `abierta`, con respuesta | `#rsvp-done` con los datos guardados y el botón MODIFICAR RESPUESTA, que abre `#rsvp-form` precargado | No |
| Enviando | Durante response | Botón ENVIAR deshabilitado, `aria-busy` | No |
| Guardada | response 200 | `#rsvp-done` con los textos actuales (`done-title`, `done-body`) | No |
| Error de red o 5xx | Falla la petición | Mensaje breve con opción de reintentar; el formulario conserva lo escrito | **Sí** (texto y presentación) |
| 429 | Rate limit | Mensaje de espera | **Sí** |
| Sin token | Sin `#t=` ni sesión | Mensaje (a) en lugar del formulario | **Sí** |
| Enlace no válido | 404 `enlace_no_valido` | Mensaje (b); se borra el token de `sessionStorage` | **Sí** |
| Cerrada sin respuesta | lookup `cerrada` | Mensaje (c) con la fecha de la configuración | **Sí** |
| Cerrada con respuesta | lookup `cerrada` con respuesta | `#rsvp-done` sin el botón MODIFICAR RESPUESTA | Sí (variante del bloque) |

Además, I-5 tendrá que aprobar el **campo de alergias** y la **línea del aviso de privacidad**, que hoy no existen en el diseño (ADR 0011).

## 8.5 Puntos de `index.html` que cambiarán en I-5

Líneas aproximadas del archivo actual:

| Línea | Hoy | Cambio previsto |
|---|---|---|
| `<head>` | — | Meta con la URL base de la API (8.3) |
| 486 | `[Nombre del invitado o familia]` y "2 lugares" | Valores de lookup, insertados como texto |
| 487 | `[fecha límite por definir]` | Fecha límite de la configuración, en formato legible en español |
| 490–513 | `<form id="rsvp-form">` sin `name` en el textarea | Nombres de campo; campo de alergias (si se aprueba); se retira el aviso "Vista previa del diseño" (l. 512) |
| 502 | `<output id="seats">2 de 2</output>` | Valor inicial a partir de los pases |
| 514–520 | `#rsvp-done` | Muestra la respuesta registrada; se retira el aviso "Vista previa" (l. 519) |
| 591 | `var assigned = 2, seats = 2;` | `assigned` = pases de la API; `seats` = confirmados vigentes, o pases si no hay respuesta |
| 598–604 | `submit` simulado | `POST response`, manejo de estados y errores |
| 605 | MODIFICAR solo alterna bloques | Además precarga la respuesta vigente |
| Nuevo bloque de script | — | Lectura del token (8.2) y lookup (8.4) |

Antes de aplicar cualquiera de estos cambios, se listarán las líneas exactas para tu aprobación (CLAUDE.md §3).

## 8.6 Lo que no cambia

- La vista previa de WhatsApp (`og:*`) sigue genérica y sin nombres.
- El resto de las secciones, animaciones, partículas, parallax y la cuenta regresiva.
- La invitación funciona sin JavaScript del RSVP: si la API no responde, todo menos el formulario sigue visible.
