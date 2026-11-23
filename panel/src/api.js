// Único cliente de la API del panel (mismo origen, ADR 0015).
// - Toda petición que no es GET lleva X-CSRF-Token (el de /auth/me); Origin lo pone el navegador.
// - Un 401 avisa a la app (sesión terminada) salvo en la consulta inicial de /auth/me.
// - Los errores llegan como ErrorApi(status, code, fields); nunca se muestran textos del servidor.

const BASE = '/api/v1'
let csrf = null
const oyentes401 = new Set()

export class ErrorApi extends Error {
  constructor(status, code, fields) {
    super(code)
    this.status = status
    this.code = code
    this.fields = fields || {}
  }
}

export function fijarCsrf(token) {
  csrf = token
}

export function alPerderSesion(fn) {
  oyentes401.add(fn)
  return () => oyentes401.delete(fn)
}

export async function pedir(metodo, ruta, opciones = {}) {
  const { json, cuerpo, tipo, params, crudo, silencioso } = opciones
  const url = new URL(BASE + ruta, window.location.origin)
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
  }
  const headers = {}
  let body
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  } else if (cuerpo !== undefined) {
    headers['Content-Type'] = tipo
    body = cuerpo
  }
  if (metodo !== 'GET' && csrf) headers['X-CSRF-Token'] = csrf
  let r
  try {
    r = await fetch(url, { method: metodo, headers, body, credentials: 'same-origin', cache: 'no-store' })
  } catch {
    throw new ErrorApi(0, 'sin_conexion')
  }
  if (!r.ok) {
    let error = {}
    try {
      error = (await r.json()).error || {}
    } catch {
      /* cuerpo no JSON */
    }
    if (r.status === 401 && !silencioso) oyentes401.forEach((fn) => fn())
    throw new ErrorApi(r.status, error.code || (r.status === 413 ? 'cuerpo_demasiado_grande' : 'error_interno'), error.fields)
  }
  if (crudo) return r
  if (r.status === 204) return null
  return r.json()
}

const enc = encodeURIComponent
const inv = (codigo, resto = '') => `/admin/invitations/${enc(codigo)}${resto}`

export const api = {
  me: () => pedir('GET', '/auth/me', { silencioso: true }),
  logout: () => pedir('POST', '/auth/logout', { silencioso: true }),
  config: () => pedir('GET', '/admin/config'),
  lista: () => pedir('GET', '/admin/invitations', { params: { incluir_archivadas: true } }),
  resumen: () => pedir('GET', '/admin/summary'),
  detalle: (c) => pedir('GET', inv(c)),
  historial: (c) => pedir('GET', inv(c, '/history')),
  auditoria: () => pedir('GET', '/admin/audit'),
  crear: (datos) => pedir('POST', '/admin/invitations', { json: datos }),
  editar: (c, datos) => pedir('PATCH', inv(c), { json: datos }),
  archivar: (c) => pedir('POST', inv(c, '/archive')),
  restaurar: (c) => pedir('POST', inv(c, '/restore')),
  desbloquear: (c, hasta) => pedir('POST', inv(c, '/unlock'), { json: { hasta } }),
  retirarDesbloqueo: (c) => pedir('DELETE', inv(c, '/unlock')),
  responder: (c, datos) => pedir('PUT', inv(c, '/response'), { json: datos }),
  verEnlace: (c) => pedir('GET', inv(c, '/link')),
  whatsappEnlace: (c, destino) => pedir('GET', inv(c, '/link/whatsapp'), { params: { destino } }),
  generarEnlace: (c) => pedir('POST', inv(c, '/link')),
  regenerarEnlace: (c) => pedir('POST', inv(c, '/link/regenerate')),
  revocarEnlace: (c) => pedir('POST', inv(c, '/link/revoke')),
  enlaceEnviado: (c, origen) => pedir('POST', inv(c, '/link/sent'), { json: { origen } }),
  recordatorio: (c, destino) => pedir('GET', inv(c, '/reminder'), { params: { destino } }),
  recordatorioEnviado: (c, destino) => pedir('POST', inv(c, '/reminder/sent'), { json: { destino } }),
  exportar: (formato, soloConfirmados) =>
    pedir('POST', '/admin/exports', { json: { formato, solo_confirmados: soloConfirmados }, crudo: true }),
  vistaPrevia: (datos, tipo, hoja, lado) =>
    pedir('POST', '/admin/imports/preview', { cuerpo: datos, tipo, params: { hoja, lado_por_defecto: lado } }),
  aplicar: (datos, tipo, hoja, lado) =>
    pedir('POST', '/admin/imports/apply', { cuerpo: datos, tipo, params: { hoja, lado_por_defecto: lado } }),
}

// Solo se abre WhatsApp con una URL https://wa.me/ que arma la API.
export function urlWhatsappSegura(url) {
  return typeof url === 'string' && url.startsWith('https://wa.me/') ? url : null
}
