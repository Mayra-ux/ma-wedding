# ADR 0014 — Usos permitidos de los ornamentos del paquete TotK

- **Estado:** Aceptado
- **Fecha:** 2026-11-02
- **Reemplaza parcialmente:** ADR 0012 (la definición de "donde ya están")

## Contexto

El ADR 0012 conservó los tres SVG del paquete "Zelda TotK Vector Bundle" con la regla "úsalos solo donde ya están", tomando como referencia el `index.html` del repositorio. Pero ese archivo se subió antes de un cambio de diseño aprobado el 31 oct 2026: la nota de "evento exclusivo para adultos" en `#vestimenta`, que usa `orn-anillo.svg` como emblema. El ADR 0012 (2 nov 2026) es posterior a esa aprobación, pero su texto no cubría el emblema.

## Decisión

Los usos permitidos de los SVG del paquete TotK son **exactamente los del diseño aprobado**:

| Sección | Archivo | Uso |
|---|---|---|
| I · Portada (`#portada`) | `orn-meandro.svg` | Ornamento de fondo con parallax, a la izquierda |
| I · Portada (`#portada`) | `orn-espirales.svg` | Ornamento de fondo con parallax, a la derecha |
| II · Aventura (`#aventura`) | `orn-anillo.svg` | Ornamento de fondo con parallax, abajo a la derecha |
| III · El gran día (`#fecha`) | `orn-espirales.svg` | Ornamento de fondo con parallax, a la izquierda (reflejado) |
| El camino (`#lugares`) | `orn-meandro.svg` | Ornamento de fondo con parallax, a la derecha |
| El camino (`#lugares`) | `orn-anillo.svg` | Ornamento de fondo con parallax, abajo a la izquierda |
| Itinerario (`#itinerario`) | `orn-espirales.svg` | Ornamento de fondo con parallax, a la derecha |
| VI · Vestimenta (`#vestimenta`) | `orn-meandro.svg` | Ornamento de fondo con parallax, a la izquierda |
| VI · Vestimenta (`#vestimenta`) | `orn-anillo.svg` | **Emblema de la nota de adultos** (detrás de la estrella) |
| Mesa de regalos (`#regalos`) | `orn-anillo.svg` | Ornamento de fondo con parallax, a la derecha |
| VII · Confirmar (`#confirmar`) | `orn-espirales.svg` | Ornamento de fondo con parallax, a la derecha |
| VIII · Cierre (`#cierre`) | `orn-anillo.svg` | Ornamento de fondo con parallax, a la izquierda |
| VIII · Cierre (`#cierre`) | `orn-espirales.svg` | Ornamento de fondo con parallax, a la derecha |

- Sigue **prohibido** agregar piezas nuevas del paquete o de otros elementos oficiales del juego, y usar las tres actuales en lugares nuevos.
- Se mantiene del ADR 0012: los SVG no se modifican, y cualquier cambio sobre ellos (reemplazo, limpieza de metadatos o retiro) requiere un ADR nuevo.

## Consecuencias

- El `index.html` del repositorio queda alineado con el diseño aprobado, incluida la nota de adultos.
- La lista de esta tabla es cerrada: un uso que no aparezca en ella requiere un ADR nuevo.
