# ADR 0009 — Importación y exportación en formato de la planner

- **Estado:** Reemplazado parcialmente por ADR 0018
- **Fecha:** 2026-11-02

> Nota: los formatos de columnas, el rol desde Comentario, la marca de revisión, los duplicados, la importación sin estado y la exportación de la planner quedan definidos por el ADR 0018. El resto de este ADR sigue vigente.

## Contexto

La planner trabaja con un Excel cuyas columnas son: No., Nombre Invitado, # Pases, Teléfono, Contacto alterno, Tel. contacto alterno, Infante, Adultos, # Niños, Invitado de, ¿Asistirá?, Pases confirmados, # de mesa, Comentario. La lista se seguirá corrigiendo después de la primera carga, y algunas filas traen # Pases distinto de Adultos + # Niños.

## Decisión

### Importación (solo novios)
- Acepta Excel o CSV con las columnas de la planner, con o sin la columna **Código INV** al inicio.
- **Repetible:**
  - Las filas con un código INV existente **se actualizan**.
  - Las filas sin código **se dan de alta**, y el panel les asigna un código nuevo.
  - Un código desconocido es **error de fila**.
- Las invitaciones del sistema que no aparecen en el archivo **no se borran**; se reportan.
- **# Pases** solo sirve para validar. Si no coincide con Adultos + # Niños, la fila se importa marcada **"requiere revisión"** y no se puede generar ni enviar su enlace hasta corregirla.
- **Invitado de** se mapea al catálogo de lado (novia / novio / ambos); un valor no reconocido marca la fila para revisión.
- Los teléfonos se normalizan a +52; un teléfono inválido marca la fila para revisión.
- **Comentario** se importa como nota interna. Si no viene la columna Rol, también sirve como fuente del rol. **La columna Rol, cuando existe, manda sobre Comentario.**
- Al reimportar un archivo exportado:
  - **Se leen:** Grupo y Rol.
  - **Se ignoran:** ¿Asistirá?, Pases confirmados, Mensaje del invitado y Alergias. Las respuestas solo cambian por el invitado o desde el panel, con historial.
- Cada importación genera un resumen (altas, actualizaciones, errores, filas en revisión) y queda auditada.

### Exportación (novios y planner)
- Columnas, en este orden: **Código INV**, las 14 columnas de la planner, y al final **Mensaje del invitado, Grupo, Rol, Alergias**.
- "Comentario" sigue siendo la nota interna.
- Las celdas que empiezan con `=`, `+`, `-` o `@` se neutralizan para evitar inyección de fórmulas al abrir el archivo en Excel.
- Cada exportación queda auditada (quién y cuándo).

## Consecuencias

- La planner sigue trabajando en su Excel, y el código INV permite el ida y vuelta sin duplicados.
- Las inconsistencias quedan visibles y bloquean el envío del enlace hasta resolverse.
- Las exportaciones contienen datos personales y salen del control del sistema; su manejo está en el ADR 0010.
- Los archivos `*.xlsx` y `*.csv` están en `.gitignore` y nunca entran al repositorio.
