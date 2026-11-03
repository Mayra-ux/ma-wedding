# ADR 0013 — Token de invitación en el fragmento de la URL

- **Estado:** Aceptado
- **Fecha:** 2026-11-02
- **Reemplaza parcialmente:** ADR 0008 (formato del enlace y reglas de las páginas `/i/`)

## Contexto

El ADR 0008 definió el enlace como `https://[dominio]/i/<token>` y exige que "los logs de la API y del hosting no registren el token". La invitación la sirve un hosting estático. Con el token en la ruta, el navegador pide `/i/<token>` al servidor, y los hostings estáticos (Vercel, Netlify, nginx…) guardan esa ruta en sus logs de acceso. La regla del ADR 0008 no se podía garantizar sin depender de un proveedor que permita filtrar esos logs. Además, `/i/<token>` exigía reglas de reescritura propias de cada hosting.

## Decisión

- **Formato del enlace:** `https://[dominio]/#t=<token>`.
  - El token sigue siendo de 128 bits aleatorios en base64url (caracteres `A–Z a–z 0–9 - _`), válidos dentro de un fragmento.
  - El prefijo `t=` evita choques con los enlaces internos de la invitación (`#aventura`, `#fecha`, `#confirmar`, etc.).
- **Comportamiento de la invitación al cargar:**
  1. El JavaScript lee `#t=<token>` del fragmento.
  2. Guarda el token en memoria y en `sessionStorage`, solo durante la visita. Los accesos a `sessionStorage` van envueltos en try/catch; si fallan, basta con la memoria.
  3. Quita el token de la barra de direcciones con `history.replaceState`, sin crear una entrada nueva en el historial.
  4. Envía el token a la API **en el cuerpo de la petición**, nunca en la URL ni en parámetros de consulta.
- **La página siempre es `/`.** No hacen falta reglas de reescritura en ningún hosting.
- **Se mantiene del ADR 0008:** hash del token para la búsqueda + copia cifrada para reenviarlo, un token por invitación, revocación y regeneración, la API nunca registra el token, rate limiting, sin IDs expuestos, vista previa de WhatsApp genérica y sin enlace para invitaciones en revisión.
- **Se reemplaza del ADR 0008:**
  - El formato `https://[dominio]/i/<token>`.
  - La regla "las páginas `/i/` llevan `Referrer-Policy: no-referrer` y `noindex`", porque esas páginas ya no existen. El fragmento nunca viaja en el encabezado `Referer` ni llega al servidor.

## Consecuencias

- Ningún log de hosting ni encabezado `Referer` contiene el token, en cualquier proveedor.
- La invitación sigue siendo portable: no requiere configuración especial del hosting.
- Si el invitado guarda un marcador después de `replaceState`, el marcador no lleva el token, así que debe volver a abrir el enlace de WhatsApp. Al recargar en la misma pestaña, el token se recupera de `sessionStorage`.
- El token sigue en el historial local del navegador y en el chat de WhatsApp; eso no cambia respecto al ADR 0008.

## Regla de envío hasta tener dominio (3 nov 2026)

- **Ningún enlace real se envía a invitados hasta definir el dominio definitivo.** El dominio queda escrito dentro de cada enlace (`https://[dominio]/#t=<token>`): un cambio posterior dejaría los enlaces ya enviados apuntando al dominio anterior.
- Mientras tanto, los enlaces solo se generan con invitaciones ficticias: en local con `http://localhost:8080` y en pruebas en la nube con `https://ma-wedding-six.vercel.app` (`INVITATION_ORIGIN`, doc 11).

## Pendientes

- **Comprobar con enlaces de prueba** que los navegadores internos de WhatsApp (iOS y Android) y los navegadores móviles principales conservan el fragmento al abrir el enlace.
- **Indexación de la raíz:** si la invitación pública debe indexarse en buscadores o no. Antes la regla `noindex` solo afectaba a `/i/`.
- **Dominio** aún sin comprar (ver ADR 0002).
