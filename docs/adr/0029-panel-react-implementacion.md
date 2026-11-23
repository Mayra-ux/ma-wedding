# ADR 0029 — Implementación del panel: seguridad del navegador, inactividad y mensajes de WhatsApp

- **Estado:** Aceptado
- **Fecha:** 2026-11-20
- **Complementa:** ADR 0003, ADR 0015 (panel servido por la API), ADR 0019, ADR 0026 (textos de los recordatorios) y ADR 0027

## Contexto

En I-9 se construye el panel React + Vite que sirve la API en `/admin/`. Lo usarán los novios y la planner, probablemente desde el celular. Hay que fijar cómo se protege en el navegador, cómo se cierra la sesión por inactividad, quién arma el mensaje de WhatsApp con el enlace y cómo se compila sin que Node sea requisito del equipo de Mayra.

## Decisión

### Construcción y dependencias
- **React 19 + Vite 8, en JavaScript (sin TypeScript)**, con enrutado por hash (`/admin/#/…`, un enrutador propio de ~40 líneas). Dependencias mínimas con versión exacta: `react` y `react-dom` (ejecución); `vite`, `@vitejs/plugin-react`, `vitest` y `jsdom` (desarrollo). Sin librerías de interfaz, de estado ni de CSS.
- **Node no se instala en el equipo:** `npm`, las pruebas y el build corren dentro del contenedor `node:24.22.3-slim` fijado por digest (`tools/check.py` y la etapa de Node del `Dockerfile`). `.npmrc` con `save-exact`, `ignore-scripts` y `engine-strict`; `npm ci --ignore-scripts`, `npm audit signatures` y `npm audit` en cada verificación.
- La imagen final **no incluye Node**: solo copia `panel/dist` a `/srv/panel` (`PANEL_DIR`). El código del panel entra al build de la imagen como contexto adicional `panel-src`.
- Fuentes Cinzel y Cormorant Garamond (licencia OFL) servidas por el panel, sin peticiones a Google; `mono.webp` es una copia sin modificar del de la invitación (lo verifica un test).

### Seguridad en el navegador
- **CSP del panel:** `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; require-trusted-types-for 'script'; trusted-types 'none'`.
- **Trusted Types:** el navegador bloquea cualquier escritura de HTML como texto (`innerHTML` y similares). El panel solo pinta texto con JSX; un test revisa que el código no use `dangerouslySetInnerHTML`, `innerHTML`, `insertAdjacentHTML`, `document.write`, `eval` ni `new Function`, y la prueba de punta a punta exige cero violaciones de CSP.
- El build no tiene scripts ni estilos en línea ni source maps. `index.html` va sin caché; `/admin/assets/*` (nombre con hash), con caché inmutable.
- Un solo cliente de la API envía `X-CSRF-Token` en toda escritura. Nada se guarda en `localStorage` ni `sessionStorage`: los datos viven en memoria.
- WhatsApp solo se abre con una URL `https://wa.me/` armada por la API, y desde un enlace real (no desde un `window.open` tras una petición, que los celulares bloquean). Abrir WhatsApp **no** marca el envío: lo marca quien envía, con un botón.
- La interfaz oculta a la planner los enlaces y los botones de escritura salvo los recordatorios; la protección real sigue en la API (ADR 0026).

### Cierre por inactividad
- Además del cierre del servidor (8 h sin actividad o 7 días), el panel cierra la sesión **a los 30 minutos sin interacción**: llama a `logout` (la sesión deja de existir en el servidor) y muestra el inicio de sesión. Se calcula con la hora de la última interacción, y se revisa al volver a la pestaña, porque el celular suspende los temporizadores.

### Fases con la hora del servidor
- `GET /api/v1/admin/config` incluye `ahora` (hora del servidor). El panel calcula con ella qué botones mostrar (plazo abierto, desbloqueo, congelamiento, cierre de la planner); quien decide sigue siendo la API.

### Mensaje de WhatsApp con el enlace (solo novios)
- Lo arma la API, igual que los recordatorios: `GET /api/v1/admin/invitations/{codigo}/link/whatsapp?destino=principal|alterno` devuelve `texto`, `telefono` y `wa_url`. Es exclusivo de los novios (la planner recibe 403) y queda en la auditoría como `enlace_consultado`, con el destino y sin el token.
- Texto aprobado por los novios:
  > Hola, {nombre}: con mucha ilusión te invitamos a nuestra boda el sábado 6 de marzo de 2027. Es peligroso ir solo… ¡acompáñanos! Aquí está tu invitación, donde puedes confirmar tu asistencia a más tardar el {fecha}:
  > {enlace}
  > Con cariño, Mayra y Alejandro

  `{nombre}` es el nombre a mostrar de la invitación y `{fecha}` sale de la configuración (hoy, «sábado 30 de enero de 2027»).
- Los textos de los recordatorios del ADR 0026 quedan **aprobados tal cual** y dejan de ser provisionales.

### Diseño
- Sobrio y funcional con la paleta y las tipografías de la invitación, mobile first (tarjetas en el celular, tabla desde 1024 px), áreas táctiles de 44 px, sin animaciones decorativas y accesible por teclado (foco visible, «Saltar al contenido», diálogos nativos que devuelven el foco).
- **Sin rojo:** los errores se muestran con «⚠», texto en bosque y borde oro-viejo sobre pergamino. Los estados llevan siempre texto y símbolo, nunca solo color.

## Consecuencias

- El panel funciona en cualquier PaaS que construya la imagen con el contexto adicional `panel-src` (`docker build --build-context panel-src=panel api`); se revisa en I-10.
- La primera consulta a `/auth/me` sin sesión deja en la consola del navegador un aviso de 401 esperado; la prueba de punta a punta lo permite solo para esa ruta.
- Cambiar un texto de WhatsApp es un cambio de la API con su prueba, no del panel.
