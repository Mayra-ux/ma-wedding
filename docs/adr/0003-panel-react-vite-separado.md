# ADR 0003 — Panel administrativo separado con React + Vite

- **Estado:** Aceptado
- **Fecha:** 2026-11-02

## Contexto

Los novios y la planner necesitan administrar invitaciones, importar y exportar la lista, ver estadísticas y preparar los mensajes de WhatsApp. Es una interfaz con mucho más estado que la invitación, y solo la usan unas pocas personas autenticadas.

## Decisión

- El panel es una **aplicación aparte construida con React + Vite**, solo para administradores.
- Consume la misma API (ADR 0002) a través de endpoints de administración protegidos (ADR 0005).
- La invitación pública **no** se migra a React ni comparte código de interfaz con el panel.
- Funciones de la v1: listado y edición de invitaciones, importación y exportación (ADR 0009), lista de pendientes y recordatorios manuales por WhatsApp, desbloqueo de invitaciones y regeneración de enlaces (ADR 0007, ADR 0008), mesa opcional y estadísticas por lado, grupo y rol.

## Consecuencias

- Aislar el panel reduce lo que expone la invitación pública.
- El panel tiene su propio build y su propio despliegue estático; el aislamiento lo da la API, no la ubicación del archivo.
- Hay dos frontends que mantener, aunque el panel es interno y no sigue el diseño congelado de la invitación.

## Pendientes

- Dónde se sirve el panel (subdominio o ruta del dominio propio) depende del dominio y del proveedor (ADR 0004).
