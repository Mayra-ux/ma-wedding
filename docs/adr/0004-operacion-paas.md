# ADR 0004 — Operación en PaaS de contenedores

- **Estado:** Aceptado
- **Fecha:** 2026-11-02

## Contexto

El sistema vive unos meses: desde el envío de invitaciones hasta el borrado final de datos (4 jun 2027, ADR 0010). Un VPS propio implica parches, firewall y monitoreo, un mantenimiento que no compensa para ese horizonte.

## Decisión

- Desplegar la API como contenedor en un **PaaS de contenedores**.
- Usar **PostgreSQL administrado**, sin acceso público a internet: solo la API se conecta, con un usuario de privilegios mínimos.
- Toda la configuración por variables de entorno; ninguna dependencia de servicios propietarios del proveedor.
- Respaldos diarios cifrados, guardados **fuera del proveedor**, con vencimiento según ADR 0010.
- La invitación estática y el panel se sirven como sitios estáticos. Vercel sigue como hosting provisional de la invitación hasta que se decida el definitivo.

## Consecuencias

- Mantenimiento de infraestructura casi nulo.
- Cambiar de proveedor equivale a desplegar la misma imagen y restaurar un respaldo.
- El costo depende del proveedor elegido.

## Pendientes

- **Proveedor del PaaS y del Postgres administrado.** Bloquea el despliegue real y la configuración de los respaldos; no bloquea el desarrollo local con Docker.
- **Dominio propio**, aún sin comprar (ver ADR 0002).
