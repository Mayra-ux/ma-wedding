# ADR 0001 — Registro de decisiones con ADRs

- **Estado:** Aceptado
- **Fecha:** 2026-11-02

## Contexto

El proyecto avanza por fases y las decisiones funcionales y técnicas se toman con los novios a lo largo de varias conversaciones. CLAUDE.md resume el estado vigente, pero no guarda el porqué de cada decisión ni su historia.

## Decisión

Registrar cada decisión relevante como un ADR (Architecture Decision Record) en `docs/adr/`.

- Nombre de archivo: `NNNN-titulo-en-minusculas.md`, numeración correlativa.
- Estructura: Estado · Fecha · Contexto · Decisión · Consecuencias · Pendientes (si los hay).
- Estados posibles: Propuesto, Aceptado, Reemplazado por ADR NNNN, Descartado.
- Un ADR aceptado no se reescribe: si la decisión cambia, se crea uno nuevo que lo reemplaza y se actualiza el estado del anterior.
- CLAUDE.md mantiene el resumen vigente y remite a estos ADRs para el detalle.
- Ningún ADR contiene datos reales de invitados (ver ADR 0010).

## Consecuencias

- Queda trazabilidad de qué se decidió, cuándo y por qué.
- Cambiar una decisión exige dejar constancia explícita.

## Índice

| ADR | Tema |
|---|---|
| 0001 | Registro de decisiones con ADRs |
| 0002 | Arquitectura: Alternativa A |
| 0003 | Panel administrativo separado con React + Vite |
| 0004 | Operación en PaaS de contenedores |
| 0005 | Acceso al panel con Google y roles |
| 0006 | Modelo de invitación y pases |
| 0007 | Respuesta, plazo e historial |
| 0008 | Enlaces y tokens de invitación |
| 0009 | Importación y exportación en formato de la planner |
| 0010 | Datos personales y retención |
| 0011 | Estados de la sección RSVP en la invitación |
| 0012 | Ornamentos del paquete TotK |
