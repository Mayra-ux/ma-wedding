# ADR 0023 — Notas de implementación en ADRs aceptados

- **Estado:** Aceptado
- **Fecha:** 2026-11-03
- **Reemplaza parcialmente:** ADR 0001 (regla "un ADR aceptado no se reescribe")

## Contexto

El ADR 0001 prohíbe reescribir un ADR aceptado: cualquier cambio exige un ADR nuevo. Al implementar las fases I-1 a I-3 aparecieron precisiones técnicas que no cambian ninguna decisión (una dependencia transitiva inerte, la herramienta de escaneo elegida, detalles de formato). Crear un ADR por cada una dispersa la información; editarlas dentro del cuerpo del ADR borra la frontera entre lo decidido y lo implementado.

## Decisión

- Un ADR aceptado puede tener, **al final**, una sección **"Notas de implementación"**.
- Solo admite precisiones técnicas que **no cambian la decisión**: versiones, detalles de formato, dependencias inertes, herramientas elegidas, referencias a ADRs que lo complementan.
- Cada nota indica la fase o la fecha en que se agregó.
- El resto del ADR (Contexto, Decisión, Consecuencias, Pendientes) **no se edita**.
- **Cualquier cambio de decisión sigue requiriendo un ADR nuevo** que reemplace total o parcialmente al anterior (ADR 0001).
- Se mantiene del ADR 0001 todo lo demás: nombres, estructura, estados, índice, CLAUDE.md como resumen vigente y ningún dato real de invitados.

## Consecuencias

- Las precisiones quedan junto a la decisión que precisan, sin alterar el texto aprobado.
- Si una nota resuelve un pendiente, el pendiente original se conserva y la nota indica cómo se resolvió.
- Distinguir "precisión" de "cambio de decisión" queda a criterio de Mayra al aprobar cada fase; ante la duda, se crea un ADR nuevo.
