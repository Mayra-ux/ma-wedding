# Panel administrativo (React + Vite)

Panel de los novios y la planner (ADR 0003, 0015, 0026, 0029). Su build lo sirve la API en `/admin/`, con enrutado por hash; nunca lo publica el hosting de la invitación, y no está dentro de `invitacion/` (ADR 0020).

## Sin Node en tu equipo

Todo corre dentro del contenedor `node:24.22.3-slim` fijado por digest:

- **Verificación completa** (lint, panel, pruebas): `cd api && uv run python tools/check.py`. Copia el panel a una carpeta del contenedor, hace `npm ci --ignore-scripts`, `npm audit signatures`, `npm audit`, las pruebas (Vitest) y el build, que queda en `panel/dist`.
- **Prueba de punta a punta** (con tu Chrome o Edge): `uv run python tools/check.py --e2e`. Con `--capturas <carpeta>` guarda las capturas de cada pantalla en 390 y 1440 px.
- **Imagen Docker:** `docker compose build api` compila el panel en una etapa de Node; la imagen final no incluye Node.

## Estructura

- `src/api.js`: único cliente de la API (CSRF en toda escritura, manejo del 401).
- `src/rutas.js`: enrutado por hash (`#/`, `#/inv/INV-001`, `#/inv/INV-001/editar`, `#/nueva`, `#/importar`, `#/exportar`, `#/actividad`).
- `src/textos.js`: todos los textos de la interfaz. Los mensajes de WhatsApp los arma la API.
- `src/filtros.js`: búsqueda, filtros y totales en el navegador (replica el resumen de la API).
- `src/inactividad.js`: cierre de sesión a los 30 min sin interacción.
- `src/pantallas/` y `src/componentes/`: pantallas y piezas de la interfaz.
- `public/`: fuentes woff2 con su licencia OFL, `mono.webp` (copia sin modificar) y `errores.css` (páginas de error del inicio de sesión).
- `test/`: pruebas de Vitest. Datos siempre ficticios.

## Reglas

- Todo texto de usuario se pinta como texto (JSX). Prohibido `dangerouslySetInnerHTML`, `innerHTML`, `eval` y similares (lo revisa `test/fuente.test.js`; en el navegador lo bloquea la CSP con Trusted Types).
- Dependencias con versión exacta y sin scripts de instalación (`.npmrc`). Agregar una requiere aprobación.
- Nada de datos personales en `localStorage` ni `sessionStorage`.
