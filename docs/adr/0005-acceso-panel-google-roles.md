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
