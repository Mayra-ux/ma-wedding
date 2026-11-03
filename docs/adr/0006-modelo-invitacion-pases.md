# ADR 0006 — Modelo de invitación y pases

- **Estado:** Aceptado
- **Fecha:** 2026-11-02

## Contexto

La lista de la planner tiene una fila por invitación (familia o grupo), con un nombre, número de pases, adultos, niños e infantes. Varias invitaciones son "nombre + acompañante" sin nombre. El evento es para adultos, con niños autorizados como excepción. En algunas filas, el número de pases no coincide con adultos + niños.

## Decisión

### Invitación
- Es la unidad del sistema: una familia o grupo, **no** una persona.
- Tiene un **nombre a mostrar** (lo único de sus datos que ve el invitado), un **código interno no secreto** (`INV-###`, asignado por el panel) y un **token** (ADR 0008).
- **Pases = adultos + niños autorizados**, con mínimo 1 adulto.
- **Infantes** (menores de 2 años, sin asiento ni alimentos): número informativo; no suman pases ni entran en la respuesta.
- **Acompañantes sin nombre:** no son una entidad; quedan implícitos en el total de pases.
- **Sin personas individuales en la v1.** Si hace falta identificar a un niño autorizado, se anota en la nota interna.

### Datos internos (el invitado no los ve)
- Lado (novia / novio / ambos), grupo (familia / amigos / trabajo) y rol en la boda (padrinos, damas, pajes, etc.), como **catálogos cerrados**.
- Mesa (opcional), nota interna y `No.` de la planner como referencia.
- Teléfono principal y contacto alterno (nombre y teléfono), **normalizados a formato internacional (+52)**. Nunca se le piden al invitado.
- Marca de **"requiere revisión"** con su motivo (ADR 0009).

### Reglas
- Solo los novios modifican pases, adultos, niños autorizados, infantes, categorías, mesa y teléfonos. El invitado nunca puede aumentar pases ni agregar niños.
- No se pueden bajar los pases por debajo de los ya confirmados sin ajustar antes la respuesta.
- Los catálogos y la consistencia de pases se garantizan en la base de datos y en la API.

## Consecuencias

- El modelo coincide con el formato de la planner, lo que simplifica importar y exportar.
- Las estadísticas por lado, grupo y rol son fiables porque los catálogos son cerrados.
- No se puede saber qué persona concreta asistirá; el banquete se planea con lo que el admin autorizó (ADR 0007).
