// @vitest-environment node
// Revisión del código fuente: ninguna vía para insertar HTML como texto ni evaluar código.
// (En el navegador, la CSP con Trusted Types lo bloquea además; ADR 0029.)
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const RAIZ = join(process.cwd(), 'src')

function archivos(dir) {
  return readdirSync(dir).flatMap((n) => {
    const ruta = join(dir, n)
    return statSync(ruta).isDirectory() ? archivos(ruta) : [ruta]
  })
}

const PROHIBIDOS = [
  /dangerouslySetInnerHTML/,
  /\.innerHTML\b/,
  /\.outerHTML\b/,
  /insertAdjacentHTML/,
  /document\.write/,
  /\beval\s*\(/,
  /new\s+Function\s*\(/,
  /setTimeout\s*\(\s*['"`]/,
  /localStorage|sessionStorage|indexedDB/,
  /\bstyle=\{/,
]

describe('código fuente del panel', () => {
  const fuentes = archivos(RAIZ).filter((r) => /\.(jsx?|css)$/.test(r))

  it('hay archivos que revisar', () => {
    expect(fuentes.length).toBeGreaterThan(10)
  })

  it.each(PROHIBIDOS.map((p) => [p.source, p]))('no usa %s', (_n, patron) => {
    const encontrados = fuentes.filter((r) => patron.test(readFileSync(r, 'utf8')))
    expect(encontrados).toEqual([])
  })

  it('sin recursos de terceros (fuentes, scripts o imágenes externas)', () => {
    const externos = fuentes.filter((r) => /https?:\/\/(?!wa\.me\/)/.test(readFileSync(r, 'utf8').replace(/^\s*\/\/.*$/gm, '')))
    expect(externos).toEqual([])
  })
})
