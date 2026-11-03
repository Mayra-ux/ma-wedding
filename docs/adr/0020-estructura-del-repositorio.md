# ADR 0020 — Estructura del repositorio

- **Estado:** Aceptado
- **Fecha:** 2026-11-02

## Contexto

Hoy la invitación vive en la raíz del repositorio, y Vercel publica la raíz completa. Al agregar el backend y el panel en el mismo repositorio, cualquier archivo en la raíz quedaría publicado en el hosting de la invitación, incluido código, configuración o documentación.

## Decisión

Estructura objetivo (se aplica en la fase I-1):

```
/
├── invitacion/         ← lo único que publica el hosting estático
│   ├── index.html
│   ├── mono-espada.webp, mono.webp, og.jpg
│   ├── orn-meandro.svg, orn-espirales.svg, orn-anillo.svg
│   └── vercel.json
├── api/                ← backend FastAPI (nunca publicado por el hosting de la invitación)
├── panel/              ← código fuente React + Vite; su build lo sirve la API (ADR 0015)
├── docs/               ← ADRs y arquitectura
├── CLAUDE.md, README.md, .gitignore
```

- La invitación y sus recursos se **mueven a `invitacion/` sin cambiar un solo byte** (se verifica comparando hashes antes y después).
- `vercel.json` se mueve con ellos, sin cambios, porque Vercel lo lee desde el Root Directory.
- **Mayra cambia el Root Directory del proyecto de Vercel a `invitacion/`.** El paso queda documentado en el README; Claude no despliega.
- Las rutas absolutas de la invitación (`/og.jpg`, `/mono.webp`) siguen funcionando, porque `invitacion/` pasa a ser la raíz publicada.
- `api/` y `panel/` nunca quedan dentro de una carpeta que publique el hosting de la invitación.

## Consecuencias

- Separación clara entre lo público (la invitación) y el código del sistema.
- Hasta que se cambie el Root Directory en Vercel, el despliegue provisional publicaría la raíz. **El cambio en Vercel debe hacerse junto con el merge de I-1.**
- Las referencias de CLAUDE.md y del README a "la raíz" se actualizan en I-1.
