# ADR 0005 — Acceso al panel con Google y roles

- **Estado:** Reemplazado parcialmente por ADR 0017
- **Fecha:** 2026-11-02

> Nota: el alcance de lectura de la planner queda precisado por el ADR 0017: ve alergias pero no los mensajes del invitado, y no ve enlaces ni la auditoría. El resto de este ADR sigue vigente.

## Contexto

El panel maneja datos personales: nombres, teléfonos y alergias. Lo usan los novios y la planner. Custodiar contraseñas y segundos factores propios añade riesgo y trabajo.

## Decisión

- **Login con Google**, restringido a listas de correos definidas en variables de entorno. Cualquier otra cuenta se rechaza.
- Dos listas, dos roles:
  - **Novios (admin):** acceso total. Editan invitaciones, importan, exportan, desbloquean, regeneran enlaces y registran respuestas en nombre de un invitado.
  - **Planner:** solo lectura + exportación.
- No se guardan contraseñas.
- Sesión con cookies `Secure`, `HttpOnly` y `SameSite`, más protección CSRF en toda operación que modifica datos.
- Los permisos se verifican en la API, nunca solo en la interfaz.
- Toda acción administrativa relevante queda auditada: quién, qué y cuándo (importación, exportación, desbloqueo, regeneración de enlace, edición).

## Consecuencias

- La seguridad de la cuenta (incluida la verificación en dos pasos) recae en Google.
- Agregar o quitar a alguien requiere cambiar una variable de entorno y reiniciar el servicio.
- La planner puede descargar exportaciones con datos personales; cada exportación queda registrada (ver ADR 0010).

## Notas de implementación

Precisiones técnicas que no cambian la decisión (ADR 0023).

- **Login con Google (I-6, 15 nov 2026):** OIDC code flow con PKCE (S256) en el servidor. El `id_token` se verifica con PyJWT 2.15.1: firma RS256 con las llaves públicas de Google, emisor, audiencia, vigencia, nonce y `email_verified`. Las peticiones a Google usan `urllib`, sin `google-auth` ni `Authlib`.
- **Cookies:** la de sesión es `__Host-ma_sesion` (`Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`). El estado de OAuth (state, nonce y verificador PKCE) viaja firmado en `__Host-ma_oauth` con **`SameSite=Lax`** y 10 min de vigencia, porque la vuelta desde Google es una navegación entre sitios y con `Strict` el navegador no la enviaría. Se borra al volver (un solo uso).
- **Roles:** en la API se llaman `admin` (novios) y `lector` (planner). Se resuelven en cada petición con las listas vigentes: si un correo deja de estar en las listas, su sesión se borra en su siguiente petición después del reinicio. Un correo en las dos listas impide que la API arranque.
- **Login rechazado:** responde 403 sin crear sesión y **no guarda el correo**, que es un dato personal de un tercero; solo queda la línea `login_denegado motivo=…` en el log. Los login y logout autorizados quedan en la auditoría.
- **Escrituras de la planner:** toda ruta de escritura de `/api/v1/admin` exige el rol `admin` por defecto. Las que la planner sí puede usar (la exportación, I-8) se marcan de forma explícita.
- **`PANEL_ORIGIN`:** origen público de la API y del panel; es la base de la URI de redirección y el valor esperado del encabezado `Origin` en las escrituras.
- **Página provisional** en `/admin/` para probar el login, hasta el panel React de I-9.
