# 8. Comunicación invitación–API

Basado en ADR 0002, 0011, 0013, 0016, 0019 y 0020. Describe el cambio **previsto** para la fase I-5. **Nada de esto se aplica ahora**, y cualquier pieza visual nueva requiere la aprobación de I-5.

## 8.1 Principios

- La invitación sigue siendo un solo `index.html` vanilla, sin build ni dependencias (ADR 0002). Desde I-1 vive en `invitacion/`, que es la carpeta publicada por el hosting (ADR 0020).
- Los cambios se limitan a la **sección VII (RSVP)** y al bloque de JavaScript que la controla. No se tocan colores, tipografías, composición ni las demás secciones (CLAUDE.md §3).
- **La página siempre se sirve en `/`.** El token va en el fragmento (`/#t=<token>`, ADR 0013), así que no hacen falta reglas de reescritura en ningún hosting.
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
- La API pública permite CORS solo desde el origen de la invitación, sin credenciales.

## 8.3 bis Encabezados de seguridad de la invitación (ADR 0019)

- **CSP:** `default-src 'none'`; `script-src` con el **hash SHA-256 del script inline** (se recalcula en cada cambio del script); `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com` (el diseño usa atributos `style`); `font-src https://fonts.gstatic.com`; `img-src 'self' data:`; `connect-src` con el origen de la API; `base-uri 'none'`.
- **`Referrer-Policy: no-referrer`**, `X-Content-Type-Options: nosniff`, HSTS y `frame-ancestors 'none'`: como encabezados del hosting cuando sea posible; si no, CSP y `referrer` como `<meta>` (sin `frame-ancestors`, que no funciona en `<meta>`).
- Es un cambio de I-5 sujeto a aprobación, y no debe alterar la apariencia.

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
| Enlace no válido | 404 `enlace_no_valido` (inexistente, revocado o archivada) | Mensaje (b); se borra el token de `sessionStorage` | **Sí** |
| Cerrada o congelada sin respuesta | lookup `cerrada` o `congelada` | Mensaje (c) con la **fecha límite global** | **Sí** |
| Cerrada o congelada con respuesta | lookup `cerrada` o `congelada` con respuesta | `#rsvp-done` sin el botón MODIFICAR RESPUESTA | Sí (variante del bloque) |

Además, I-5 tendrá que aprobar el **campo de alergias** y la **línea del aviso de privacidad**, que hoy no existen en el diseño (ADR 0011).

## 8.5 Puntos de `index.html` que cambiarán en I-5

Líneas aproximadas del archivo actual (con la nota de adultos ya insertada; la ruta será `invitacion/index.html` desde I-1):

| Línea | Hoy | Cambio previsto |
|---|---|---|
| `<head>` (hasta l. 276) | — | Meta con la URL base de la API (8.3) y, si el hosting no envía encabezados, CSP y `referrer` (8.3 bis) |
| 500 | `[Nombre del invitado o familia]` y "2 lugares" | Valores de lookup, insertados como texto |
| 501 | `[fecha límite por definir]` | Fecha límite de la configuración, en formato legible en español |
| 504–527 | `<form id="rsvp-form">` sin `name` en el textarea | Nombres de campo, `maxlength` (mensaje 500, alergias 200); campo de alergias (si se aprueba); se retira el aviso "Vista previa del diseño" (l. 526) |
| 516 | `<output id="seats">2 de 2</output>` | Valor inicial a partir de los pases |
| 528–534 | `#rsvp-done` | Muestra la respuesta registrada; se retira el aviso "Vista previa" (l. 533) |
| 605 | `var assigned = 2, seats = 2;` | `assigned` = pases de la API; `seats` = confirmados vigentes, o pases si no hay respuesta |
| 612–618 | `submit` simulado | `POST response`, manejo de estados y errores |
| 619 | MODIFICAR solo alterna bloques | Además precarga la respuesta vigente |
| Nuevo bloque de script | — | Lectura del token (8.2) y lookup (8.4) |

Antes de aplicar cualquiera de estos cambios, se listarán las líneas exactas para tu aprobación (CLAUDE.md §3).

## 8.6 Lo que no cambia

- La vista previa de WhatsApp (`og:*`) sigue genérica y sin nombres.
- El resto de las secciones, animaciones, partículas, parallax y la cuenta regresiva.
- La invitación funciona sin JavaScript del RSVP: si la API no responde, todo menos el formulario sigue visible.
