# ADR 0015 — Panel servido por la propia API (mismo origen)

- **Estado:** Aceptado
- **Fecha:** 2026-11-02
- **Reemplaza parcialmente:** ADR 0003 (el despliegue estático propio del panel)

## Contexto

El ADR 0003 definía el panel como una aplicación React + Vite con despliegue estático propio. En la validación de la Fase 3 apareció un problema: si el panel y la API quedan en sitios distintos, el navegador trata la cookie de sesión como de terceros. Safari y Chrome la bloquean y el login falla, salvo que se use un dominio propio con subdominios y CORS con credenciales. Además, una aplicación React con rutas por path necesita reglas de reescritura en cualquier hosting estático.

## Decisión

- El panel sigue siendo **React + Vite con build propio**, pero sus archivos compilados los **sirve la propia API**, en el mismo origen (p. ej. `https://api.[dominio]/admin/`).
- **Enrutado por hash** (`/admin/#/invitaciones`), para que no haga falta ninguna regla de reescritura.
- La imagen Docker de la API incluye el build del panel. El panel no tiene un despliegue separado.
- Al ser el mismo origen, **no hay CORS para el panel**. CORS solo existe para la invitación pública y nunca acepta credenciales.
- La cookie de sesión puede usar `SameSite=Strict` y el prefijo `__Host-`.
- Se mantiene del ADR 0003: aplicación aparte solo para administradores, sin compartir código con la invitación, y las mismas funciones de la v1.

## Consecuencias

- Se elimina el problema de las cookies de terceros, y el panel funciona sin dominio propio (por ejemplo, en el dominio que asigne el PaaS durante las pruebas).
- Un despliegue menos: la versión del panel siempre coincide con la de la API.
- La imagen Docker requiere un paso de compilación del panel (Node solo en la etapa de build; la imagen final no lo incluye).
- La invitación sigue en un hosting estático aparte (ADR 0002, ADR 0020).
