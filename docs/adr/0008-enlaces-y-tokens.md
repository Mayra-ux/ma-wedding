# ADR 0008 — Enlaces y tokens de invitación

- **Estado:** Aceptado
- **Fecha:** 2026-11-02

## Contexto

Cada invitación se identifica con un enlace personal que se envía por WhatsApp. El repositorio es público y el enlace es la única llave del invitado. Los novios necesitan poder reenviar el mismo enlace desde el panel.

## Decisión

- **Formato:** `https://[dominio]/i/<token>`.
- **Token:** 128 bits aleatorios de un generador criptográfico, codificados en base64url. **Uno por invitación** (familia o grupo), no por persona.
- **Almacenamiento:**
  - El **hash** del token, para buscar la invitación.
  - Una **copia cifrada**, para que el panel pueda volver a mostrar y reenviar el mismo enlace. La llave de cifrado vive en una variable de entorno, nunca en el repositorio ni en la base de datos.
- **Revocación:** los novios pueden revocar y regenerar el enlace de una invitación; el anterior deja de funcionar al instante.
- **Sin código adicional:** cualquiera que tenga el enlace puede consultar y responder (decisión aceptada).
- **Sin identificadores expuestos:** las respuestas públicas nunca incluyen IDs internos, IDs secuenciales ni el código `INV-###`.
- **Protección contra filtraciones:**
  - Las páginas `/i/` llevan `Referrer-Policy: no-referrer` (protege los enlaces salientes a Maps y Liverpool) y `noindex`.
  - Los logs de la API y del hosting no registran el token.
- **Límite de peticiones** en la consulta y el envío por token.
- No se genera ni se comparte el enlace de una invitación marcada "requiere revisión" (ADR 0009).
- La vista previa de WhatsApp (`og:*`) es genérica y nunca muestra nombres de invitados.

## Consecuencias

- Adivinar un token es inviable (2^128 combinaciones).
- Si se pierde la llave de cifrado, no se podrán reenviar los enlaces existentes: habrá que regenerarlos y volver a enviarlos.
- Un enlace reenviado por el invitado da acceso a terceros; los novios aceptan ese riesgo y el historial deja rastro de cada cambio.

## Pendientes

- **Dominio** aún sin comprar: el formato final del enlace y las URLs absolutas de `og:url` y `og:image` dependen de él.
