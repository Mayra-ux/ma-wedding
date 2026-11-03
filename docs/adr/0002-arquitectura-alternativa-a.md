# ADR 0002 — Arquitectura: Alternativa A

- **Estado:** Aceptado
- **Fecha:** 2026-11-02

## Contexto

La invitación es hoy un sitio estático (un solo `index.html`, sin framework ni build) con diseño aprobado y congelado. El formulario RSVP está simulado. Hace falta guardar respuestas, administrar la lista de invitados y operar el sistema unos meses, sin quedar atados a un proveedor. El despliegue actual en Vercel es provisional.

## Decisión

Adoptar la **Alternativa A**:

- **Invitación:** el sitio estático actual. Sigue sin framework (HTML + CSS + JS vanilla, sin build). La conexión con el backend se hace con JavaScript vanilla sobre el formulario existente, con cambios mínimos y quirúrgicos en `index.html`.
- **API:** FastAPI (Python), empaquetada en un contenedor Docker.
- **Base de datos:** PostgreSQL estándar, sin extensiones propietarias.
- **Panel administrativo:** aplicación aparte (ver ADR 0003).
- **Configuración:** solo por variables de entorno; secretos fuera del repositorio (`.env` ignorado, `.env.example` con valores ficticios).
- **Galería futura:** solo fotos de la sesión de pareja; fuera del alcance actual.

## Consecuencias

- La invitación conserva su diseño y su rendimiento; el backend se puede mover de proveedor sin tocarla.
- Docker es el mecanismo de portabilidad: la misma imagen corre en local y en el hosting definitivo.
- La invitación y la API pueden vivir en orígenes distintos, lo que obliga a configurar CORS de forma restrictiva.
- Vercel se usa solo como hosting estático provisional; no se usan funciones propietarias.

## Pendientes

- Dominio propio: decidido, aún sin comprar. Determina los orígenes permitidos (CORS), las cookies y las URLs absolutas de `og:url` / `og:image`.
- Proveedor de hosting: ver ADR 0004.
