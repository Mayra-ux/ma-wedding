# ADR 0017 — Reglas de invitación, catálogos y permisos del panel

- **Estado:** Aceptado
- **Fecha:** 2026-11-02
- **Reemplaza parcialmente:** ADR 0006 (rol único, borrado de invitaciones, catálogos y longitudes) y ADR 0005 (alcance de lectura de la planner)

## Contexto

La validación de la Fase 3 dejó reglas de la invitación y del panel sin definir: borrado, número de roles, valores de los catálogos, longitudes máximas, qué pasa con las alergias si no asiste, qué ve la planner y cómo se sabe a quién ya se le envió el enlace.

## Decisión

### Invitaciones
- **No se borran: se archivan.** Al archivar, el enlace se revoca, la invitación sale de los conteos y estadísticas, y sus datos se purgan el 4 jun 2027 junto con los demás (ADR 0010). Una invitación archivada se puede restaurar antes del congelamiento, pero necesita un enlace nuevo.
- Se permiten **invitaciones sin teléfono**; el panel muestra un aviso.
- **Varios roles por invitación.**
- **Longitudes máximas:** nombre a mostrar 120 · mensaje 500 · alergias 200 · nota interna 500 caracteres.

### Catálogos (valores cerrados)
- **Lado:** Novia, Novio, Ambos.
- **Grupo** (uno por invitación): Familia, Amigos, Trabajo, Otro.
- **Rol en la boda** (cero, uno o varios por invitación): Papás de la novia, Papás del novio, Hermano/a de la novia, Hermano/a del novio, Padrinos de velación, Padrinos de lazo, Padrinos de arras, Padrinos de anillos, Dama de honor, Caballero del novio, Paje, Ofrendas, Otro.

### Respuesta
- Si la respuesta es "no asiste", **se vacían las alergias** y **se conserva el mensaje**.

### Envío del enlace
- Cada invitación registra si su enlace fue **enviado**, con fecha y origen:
  - **Automático** al usar el botón de WhatsApp del panel.
  - **Manual**, marcándolo a mano.
- La lista de recordatorios muestra las invitaciones con enlace enviado y sin respuesta.
- El panel ofrece WhatsApp **al teléfono principal y al contacto alterno**.
- Regenerar el enlace reinicia la marca de enviado.

### Permisos de la planner (precisa el ADR 0005)
- La planner **ve las alergias** y **no ve los mensajes del invitado**: ni en el listado, ni en el detalle, ni en el historial, ni en su exportación.
- Tampoco ve ni gestiona enlaces, no usa WhatsApp desde el panel y no ve la auditoría.
- Se mantiene: solo lectura + exportación.

## Consecuencias

- Las estadísticas por rol cuentan una invitación en cada uno de sus roles.
- La exportación de la planner omite la columna "Mensaje del invitado" (ADR 0018).
- Archivar en vez de borrar respeta la inmutabilidad del historial (ADR 0007).
