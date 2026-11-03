# Invitación M&A

Invitación digital de la boda de Mayra y Alejandro. Sitio estático sin build ni dependencias:
HTML, CSS y JavaScript vanilla en un solo `index.html`.

## Estructura

Todos los archivos viven en la raíz del repositorio:

- `index.html` — página completa (estilos y scripts incluidos).
- `mono-espada.webp` — monograma con espada (portada y cierre).
- `mono.webp` — monograma sin espada (navegación y favicon).
- `orn-meandro.svg`, `orn-espirales.svg`, `orn-anillo.svg` — ornamentos.
- `og.jpg` — imagen de vista previa para compartir (1200×630).
- `vercel.json` — URLs limpias y caché de imágenes.

## Ramas

- `main` — versión publicada.
- `develop` — rama de trabajo; los cambios se integran a `main` mediante merge.

## Ver en local

Cualquier servidor estático desde la raíz, por ejemplo:

    python -m http.server 8000

y abrir http://localhost:8000.

## Despliegue

Despliegue provisional en Vercel como sitio estático desde la raíz:
Framework preset "Other", sin build command ni output directory.
