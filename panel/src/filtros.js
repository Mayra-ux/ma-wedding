// Búsqueda, filtros y totales calculados en el navegador con la lista completa (doc 13, I-9).
// `calcularResumen` replica el resumen de la API (app/invitaciones.py:resumen); un test de
// punta a punta verifica que coinciden.
import { GRUPOS, LADOS, ROLES_BODA } from './catalogos.js'

export function normalizar(texto) {
  return String(texto ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
}

export const FILTROS_INICIALES = {
  texto: '',
  estado: '',
  lado: '',
  grupo: '',
  rol: '',
  revision: '',
  enlace: '',
  archivadas: false,
}

export function hayFiltros(f) {
  return Object.entries(FILTROS_INICIALES).some(([k, v]) => f[k] !== v)
}

export function coincide(fila, f) {
  if (!f.archivadas && fila.archivada) return false
  if (f.texto) {
    const q = normalizar(f.texto)
    const pajar = normalizar(`${fila.codigo} ${fila.nombre_mostrar} ${fila.no_planner ?? ''}`)
    if (!q.split(' ').every((p) => pajar.includes(p))) return false
  }
  if (f.estado && fila.estado_respuesta !== f.estado) return false
  if (f.lado && (fila.lado || 'sin_lado') !== f.lado) return false
  if (f.grupo && (fila.grupo || 'sin_grupo') !== f.grupo) return false
  if (f.rol && !fila.roles.includes(f.rol)) return false
  if (f.revision === 'si' && !fila.requiere_revision) return false
  if (f.revision === 'no' && fila.requiere_revision) return false
  if (f.enlace === 'enviado' && !fila.enlace_enviado) return false
  if (f.enlace === 'no_enviado' && (fila.enlace_enviado || !fila.enlace_activo)) return false
  if (f.enlace === 'sin_enlace' && fila.enlace_activo) return false
  return true
}

export function filtrar(filas, f) {
  return filas.filter((fila) => coincide(fila, f))
}

const vacio = () => ({ invitaciones: 0, pases: 0, confirmados: 0 })
const cubos = (claves) => Object.fromEntries(claves.map((k) => [k, vacio()]))

export function calcularResumen(filas) {
  const activas = filas.filter((f) => !f.archivada)
  const r = {
    invitaciones: activas.length,
    pases_asignados: 0,
    personas_confirmadas: 0,
    ninos_autorizados: 0,
    infantes: 0,
    por_estado: cubos(['confirmada', 'no_asiste', 'pendiente']),
    por_lado: cubos([...LADOS, 'sin_lado']),
    por_grupo: cubos([...GRUPOS, 'sin_grupo']),
    por_rol: cubos(ROLES_BODA),
  }
  for (const f of activas) {
    const confirmados = f.confirmados || 0
    r.pases_asignados += f.pases
    r.personas_confirmadas += confirmados
    r.ninos_autorizados += f.ninos_autorizados
    r.infantes += f.infantes
    const destino = [
      r.por_estado[f.estado_respuesta],
      r.por_lado[f.lado || 'sin_lado'],
      r.por_grupo[f.grupo || 'sin_grupo'],
      ...f.roles.map((rol) => r.por_rol[rol]),
    ]
    for (const c of destino) {
      c.invitaciones += 1
      c.pases += f.pases
      c.confirmados += confirmados
    }
  }
  return r
}
