# ADR 0001 — Registro de decisiones con ADRs

- **Estado:** Reemplazado parcialmente por ADR 0023
- **Fecha:** 2026-11-02

> Nota: el ADR 0023 permite una sección final "Notas de implementación" en ADRs aceptados, solo para precisiones técnicas que no cambian la decisión. El resto de este ADR sigue vigente.

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
| 0013 | Token de invitación en el fragmento de la URL (reemplaza parcialmente al 0008) |
| 0014 | Usos permitidos de los ornamentos del paquete TotK (reemplaza parcialmente al 0012) |
| 0015 | Panel servido por la propia API, mismo origen (reemplaza parcialmente al 0003) |
| 0016 | Plazo, desbloqueo y congelamiento del RSVP (reemplaza parcialmente al 0007 y al 0011) |
| 0017 | Reglas de invitación, catálogos y permisos del panel (reemplaza parcialmente al 0005 y al 0006) |
| 0018 | Importación y exportación: formatos y simplificación (reemplaza parcialmente al 0009) |
| 0019 | Endurecimiento de seguridad y operación (complementa al 0004, 0005, 0008, 0010 y 0015) |
| 0020 | Estructura del repositorio |
| 0021 | Envío de enlaces hasta tener dominio definitivo (complementa al 0008 y al 0013) |
| 0022 | Implementación de tokens y rotación de llaves (complementa al 0019 y al 0008) |
| 0023 | Notas de implementación en ADRs aceptados (reemplaza parcialmente al 0001) |
