# ADR 0018 — Importación y exportación: formatos y simplificación

- **Estado:** Aceptado
- **Fecha:** 2026-11-02
- **Reemplaza parcialmente:** ADR 0009 (formatos de columnas, rol desde Comentario, marca de revisión, duplicados, columnas de la exportación de la planner)

## Contexto

El ADR 0009 dejaba sin definir los formatos de las columnas de la planner, cómo obtener el rol del texto libre de "Comentario", cómo se resuelve la marca de revisión y qué pasa con los duplicados. Para 33 invitaciones, guardar en la DB lotes y filas de importación es innecesario.

## Decisión

### Formatos de columnas (importación y exportación)
| Columna | Formato |
|---|---|
| Infante | Número entero ≥ 0 |
| ¿Asistirá? | `Sí`, `No` o vacío (pendiente) |
| Pases confirmados | Número; **vacío si está pendiente**; `0` si no asiste |
| Invitado de | `Novia`, `Novio` o `Ambos` |
| # Pases | Al exportar: **calculado** (adultos + niños). Al importar: solo sirve para validar |
| Rol (columna extra) | Valores del catálogo separados por `;` (varios roles, ADR 0017) |
| Grupo (columna extra) | Un valor del catálogo |

Los valores se comparan tras quitar espacios al inicio y al final; cualquier otra diferencia los hace inválidos y marca la fila para revisión.

### Rol desde "Comentario"
- Si no viene la columna Rol: cuando el texto de Comentario **coincide exactamente** con un valor del catálogo, es el rol; en cualquier otro caso, es nota interna.
- Si viene la columna Rol, esta manda y Comentario es siempre nota interna.

### Marca "requiere revisión"
- Se guarda el **"# Pases" original** de la planner.
- La marca **se quita sola** cuando se corrige la inconsistencia que la causó (adultos + niños = # Pases original, lado o teléfono válidos), o cuando los novios ajustan adultos y niños y aceptan el nuevo total.

### Duplicados
- Las filas sin código con un nombre a mostrar igual al de otra invitación o fila generan **solo un aviso**: se importan.

### Importación sin estado (simplificación)
- **Vista previa:** se sube el archivo, la API devuelve el resultado por fila y no guarda nada.
- **Aplicar:** se vuelve a subir el mismo archivo y se aplica en una sola transacción.
- Solo se audita el resumen (conteos, quién y cuándo). No se guardan lotes ni filas en la DB.

### Exportación
- **Novios:** Código INV + 14 columnas de la planner + Mensaje del invitado, Grupo, Rol, Alergias (19 columnas).
- **Planner:** las mismas, **sin "Mensaje del invitado"** (18 columnas, ADR 0017).
- Las invitaciones archivadas no se exportan.
- Se mantienen: protección contra fórmulas y auditoría de cada exportación.

## Consecuencias

- La planner puede trabajar con su formato sin ambigüedades.
- Hay menos tablas y menos datos personales guardados (el resultado por fila no se conserva).
- Para aplicar hay que volver a subir el archivo; con 33 filas no supone ningún costo.
