# 9. Estrategia de imágenes para la futura galería

Basado en ADR 0002 y en CLAUDE.md §3. **No se prepara la galería hasta que se pida**; esto es solo la estrategia.

## Alcance

- Solo fotografías profesionales de la **sesión de pareja**. No hay fotos de invitados, subidas por usuarios, stock ni imágenes generadas por IA.
- Las fotos son contenido público del sitio estático. No pasan por la API ni por la base de datos y no tienen relación con datos de invitados.

## Preparación antes de publicar

| Paso | Detalle |
|---|---|
| Selección | Los novios eligen las fotos y su orden; no se inventa ni se completa nada |
| **Quitar metadatos** | Eliminar EXIF, GPS, número de serie de la cámara y miniaturas incrustadas. Es obligatorio por privacidad: el GPS revelaría lugares |
| Formatos | AVIF y WebP, con JPEG como respaldo solo si se necesita compatibilidad |
| Tamaños | Varias anchuras por foto (p. ej. 480, 800, 1200, 1600 px) para `srcset`/`sizes`; mobile first |
| Compresión | Calidad ajustada a mano, revisando que no haya bandas en tonos de piel ni en cielos |
| Color | Convertir a sRGB |
| Nombres | Con versión en el nombre (p. ej. `sesion-03.a1b2c3.webp`), para poder usar caché larga sin el problema que corrigió la limpieza de `vercel.json` |

## Publicación

- Imágenes servidas como archivos estáticos del mismo hosting de la invitación. Sin CDN de procesamiento de terceros ni servicios de transformación propietarios (portabilidad, ADR 0002).
- `<img>` con `srcset`, `sizes`, `width` y `height` explícitos (evita saltos de diseño), `loading="lazy"` y `decoding="async"`. La primera imagen visible no se carga en diferido.
- Texto alternativo descriptivo y breve para cada foto (accesibilidad, CLAUDE.md §3), redactado o aprobado por los novios.
- Si hay visor ampliado: navegable con teclado, con foco visible y respetando `prefers-reduced-motion`.

## Herramienta de generación

- Hoy la invitación no tiene build. Para generar tamaños y nombres versionados, CLAUDE.md prevé como posibilidad **Vite sin framework**, siempre que la página se vea idéntica.
- **Sugerencia:** si el número de fotos es pequeño, basta con generar los archivos una vez con una herramienta local y subirlos ya optimizados, sin agregar un build al sitio. La decisión se toma cuando se pida la galería, con un ADR.

## Diseño

- La sección de galería, su ubicación y su estilo requieren aprobación explícita: el diseño está congelado (CLAUDE.md §3).
