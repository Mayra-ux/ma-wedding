# Arquitectura conceptual — Invitación M&A

Diseño conceptual del sistema RSVP de la invitación (Fase 2). Describe **qué** se construye y **dónde** se garantiza cada regla, sin código, SQL, migraciones ni configuración.

## Fuentes

- [CLAUDE.md](../../CLAUDE.md): contexto permanente, diseño congelado y reglas del proyecto.
- [ADRs 0001–0013](../adr/): decisiones aceptadas. Si este documento y un ADR difieren, **manda el ADR**, y la diferencia se resuelve con un ADR nuevo.

## Convenciones

- **Garantía:** dónde se asegura una regla.
  - **DB**: la base de datos la impone (restricciones, unicidad, consistencia).
  - **API**: la impone el servidor FastAPI.
  - **Ambas**: la API valida y la DB la respalda como última defensa.
  - La interfaz (invitación o panel) **nunca** es garantía; solo ayuda al usuario.
- **Origen:** cada regla cita su ADR (p. ej. `ADR 0007`). Lo que no sale de un ADR va marcado como **sugerencia** y requiere aprobación antes de implementarse.
- **Datos:** todos los ejemplos son ficticios (`INV-001`, "Familia Ejemplo"). Nunca se usan datos reales (ADR 0010).
- **Diagramas:** Mermaid; se ven en GitHub y en la vista previa de Markdown de VS Code.
- **Enlace de invitación:** `https://[dominio]/#t=<token>` (ADR 0013).

## Mapa de documentos

| # | Documento | Contenido |
|---|---|---|
| 1 | [01-componentes.md](01-componentes.md) | Diagrama general de componentes, orígenes y límites de confianza |
| 2 | [02-modelo-de-datos.md](02-modelo-de-datos.md) | Entidades, atributos, relaciones, cardinalidades, restricciones y clasificación para el borrado |
| 3 | [03-flujos-invitado.md](03-flujos-invitado.md) | Secuencias del invitado: confirmar, modificar, exceder pases, estados de error |
| 4 | [04-flujos-admin.md](04-flujos-admin.md) | Secuencias del panel: desbloqueo, enlaces, WhatsApp, importación, exportación, borrado programado |
| 5 | [05-reglas-de-negocio.md](05-reglas-de-negocio.md) | Catálogo de reglas con su garantía y ADR de origen |
| 6 | [06-autenticacion-autorizacion.md](06-autenticacion-autorizacion.md) | Token del invitado, login con Google, roles, sesiones, cookies, CSRF |
| 7 | [07-contratos-api.md](07-contratos-api.md) | Contratos conceptuales de la API pública y de la API del panel |
| 8 | [08-invitacion-api.md](08-invitacion-api.md) | Comunicación invitación–API y cambio mínimo previsto en `index.html` |
| 9 | [09-galeria-imagenes.md](09-galeria-imagenes.md) | Estrategia de imágenes para la futura galería de la sesión de pareja |
| 10 | [10-respaldos.md](10-respaldos.md) | Respaldos, restauración y vencimientos alineados con el borrado |
| 11 | [11-despliegue.md](11-despliegue.md) | Imagen Docker única, variables de entorno y comparación de opciones de hosting |
| 12 | [12-riesgos-y-preguntas.md](12-riesgos-y-preguntas.md) | Riesgos y preguntas abiertas |

## Estado

- Fase 2: documentación conceptual. Nada de esto está implementado.
- Ningún cambio visual a la invitación se aplica sin la aprobación de la fase I-5 (ADR 0011).
