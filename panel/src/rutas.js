// Enrutado por hash (ADR 0015): /admin/#/..., sin reglas de reescritura en el servidor.
import { useEffect, useState } from 'react'

const CODIGO = /^INV-\d{3,}$/

export function leerRuta(hash) {
  const partes = (hash || '').replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent)
  if (partes.length === 0) return { nombre: 'lista' }
  const [a, b, c] = partes
  if (partes.length === 1 && ['nueva', 'importar', 'exportar', 'actividad'].includes(a)) return { nombre: a }
  if (a === 'inv' && CODIGO.test(b || '')) {
    if (partes.length === 2) return { nombre: 'detalle', codigo: b }
    if (partes.length === 3 && c === 'editar') return { nombre: 'editar', codigo: b }
  }
  return { nombre: 'no_encontrada' }
}

export const enlaces = {
  lista: '#/',
  nueva: '#/nueva',
  importar: '#/importar',
  exportar: '#/exportar',
  actividad: '#/actividad',
  detalle: (codigo) => `#/inv/${encodeURIComponent(codigo)}`,
  editar: (codigo) => `#/inv/${encodeURIComponent(codigo)}/editar`,
}

export function ir(hash) {
  window.location.hash = hash
}

export function useRuta() {
  const [ruta, setRuta] = useState(() => leerRuta(window.location.hash))
  useEffect(() => {
    const cambiar = () => setRuta(leerRuta(window.location.hash))
    window.addEventListener('hashchange', cambiar)
    return () => window.removeEventListener('hashchange', cambiar)
  }, [])
  return ruta
}
