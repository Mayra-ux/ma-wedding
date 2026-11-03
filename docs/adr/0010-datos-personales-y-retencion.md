# ADR 0010 — Datos personales y retención

- **Estado:** Aceptado
- **Fecha:** 2026-11-02

## Contexto

El sistema guarda nombres, teléfonos, alergias (dato de salud, sensible según la LFPDPPP) y mensajes. El repositorio es público. Los datos solo se necesitan hasta poco después de la boda (6 mar 2027).

## Decisión

### Datos reales fuera del repositorio
- El Excel de la lista vive fuera del repositorio.
- Ningún nombre ni teléfono real aparece en código, pruebas, seeds, documentación ni commits. Los datos de desarrollo son siempre ficticios.
- `*.xlsx` y `*.csv` están en `.gitignore`.

### Minimización
- Al invitado solo se le piden el total de asistentes, alergias (opcional, una por invitación) y mensaje (opcional).
- Los teléfonos los cargan los novios; nunca se le piden al invitado.

### Calendario post-boda
1. **Antes del 5 abr 2027:** congelar el RSVP, hacer la exportación final y el respaldo final.
2. **5 abr 2027 (boda + 30 días):** borrar **alergias y teléfonos** (principal y contacto alterno), **también en el historial de respuestas**.
3. **4 jun 2027 (boda + 90 días):** borrar el **resto de los datos personales**: nombres, mensajes, notas internas, historial, enlaces y registros de auditoría con datos personales.
4. Apagar la API y la base de datos.

### Respaldos
- Todo respaldo vence en la fecha de borrado del dato más restrictivo que contenga.
- Los respaldos que contienen teléfonos o alergias vencen el **5 abr 2027**; los posteriores sin esos datos vencen el **4 jun 2027**.

### Exportación final descargada
- La exportación final contiene teléfonos y alergias. **El 5 abr 2027 ese archivo se borra, o se reemplaza por una versión sin esas columnas.**
- Lo mismo aplica a cualquier otra exportación descargada por los novios o la planner.

### Seguridad del contenido
- Todo texto que viene del invitado o del Excel se trata como texto, nunca como HTML, en la invitación, en el panel y en las exportaciones.

## Consecuencias

- Después del 5 abr 2027 no queda ningún teléfono ni alergia en el sistema, en los respaldos ni en la exportación final.
- Después de esa fecha no se puede restaurar el estado previo con esos datos.
- El borrado de las exportaciones descargadas depende de un proceso manual de los novios y la planner; el sistema solo puede registrar quién exportó y cuándo.

## Pendientes

- **Aviso de privacidad:** decidido como una línea breve junto al formulario, con enlace a un aviso corto. Falta el texto y el nombre del responsable de los datos. Bloquea la publicación del RSVP real.
- La aprobación visual de esa línea forma parte de la fase I-5 (ADR 0011).
