# ADR 0021 — Envío de enlaces hasta tener dominio definitivo

- **Estado:** Aceptado
- **Fecha:** 2026-11-03
- **Complementa:** ADR 0008 y 0013

## Contexto

El enlace de cada invitación tiene la forma `https://[dominio]/#t=<token>` (ADR 0013) y se arma con `INVITATION_ORIGIN` (doc 11). El dominio propio aún no se compra (ADR 0002, 0008). La fase I-3 ya permite generar enlaces, y existe un despliegue provisional en Vercel (`ma-wedding-six.vercel.app`).

Un enlace enviado por WhatsApp lleva el dominio escrito dentro. Si después el dominio cambia, el panel mostraría los enlaces con el dominio nuevo (el token es el mismo), pero los que ya se enviaron seguirían apuntando al anterior, que tendría que seguir sirviendo la invitación indefinidamente.

## Decisión

- **Ningún enlace real se envía a invitados hasta definir el dominio definitivo.**
- Mientras tanto, los enlaces solo se generan con invitaciones ficticias:
  - Local: `INVITATION_ORIGIN=http://localhost:8080`.
  - Pruebas en la nube: `INVITATION_ORIGIN=https://ma-wedding-six.vercel.app`.
- El dominio definitivo se configura en `INVITATION_ORIGIN` antes de generar el primer enlace real.

## Consecuencias

- Los enlaces enviados a invitados no dependen de un dominio provisional.
- El envío real de enlaces queda bloqueado por la compra del dominio, además de por los bloqueos ya existentes (aviso de privacidad, aprobación de I-5; checklist de I-10).
- La prueba del fragmento en WhatsApp (ADR 0013, pendiente) se hace con enlaces ficticios sobre el dominio de pruebas.

## Pendientes

- Compra del dominio definitivo.
