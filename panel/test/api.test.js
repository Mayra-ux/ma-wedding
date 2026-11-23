import { afterEach, describe, expect, it, vi } from 'vitest'
import { ErrorApi, alPerderSesion, api, fijarCsrf } from '../src/api.js'

function respuesta(status, cuerpo) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => cuerpo,
    headers: new Headers(),
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
  fijarCsrf(null)
})

describe('cliente de la API', () => {
  it('las lecturas no llevan CSRF; toda escritura sí', async () => {
    const llamadas = []
    vi.stubGlobal('fetch', vi.fn(async (url, op) => {
      llamadas.push([String(url), op])
      return respuesta(200, {})
    }))
    fijarCsrf('csrf-ficticio')
    await api.lista()
    await api.archivar('INV-001')
    await api.editar('INV-001', { mesa: 3 })
    await api.retirarDesbloqueo('INV-001')
    await api.recordatorioEnviado('INV-001', 'principal')
    await api.vistaPrevia(new ArrayBuffer(1), 'text/csv', null, 'Novia')
    const [get, ...escrituras] = llamadas
    expect(get[0]).toBe('http://localhost:3000/api/v1/admin/invitations?incluir_archivadas=true')
    expect(get[1].headers['X-CSRF-Token']).toBeUndefined()
    expect(get[1].credentials).toBe('same-origin')
    for (const [, op] of escrituras) expect(op.headers['X-CSRF-Token']).toBe('csrf-ficticio')
    expect(escrituras.map(([, op]) => op.method)).toEqual(['POST', 'PATCH', 'DELETE', 'POST', 'POST'])
    expect(escrituras[4][0]).toBe('http://localhost:3000/api/v1/admin/imports/preview?lado_por_defecto=Novia')
    expect(escrituras[4][1].headers['Content-Type']).toBe('text/csv')
  })

  it('el código de invitación se codifica en la URL', async () => {
    const urls = []
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      urls.push(String(url))
      return respuesta(200, {})
    }))
    await api.detalle('INV-001/../../auth/logout')
    expect(urls[0]).toBe('http://localhost:3000/api/v1/admin/invitations/INV-001%2F..%2F..%2Fauth%2Flogout')
  })

  it('un 401 avisa a la app (salvo en /auth/me) y los errores llevan solo el código', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => respuesta(401, { error: { code: 'no_autenticado', message: 'x' } })))
    const perdida = vi.fn()
    const quitar = alPerderSesion(perdida)
    await expect(api.me()).rejects.toMatchObject({ status: 401, code: 'no_autenticado' })
    expect(perdida).not.toHaveBeenCalled()
    await expect(api.lista()).rejects.toBeInstanceOf(ErrorApi)
    expect(perdida).toHaveBeenCalledTimes(1)
    quitar()
  })

  it('campos de validación y error de red', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => respuesta(422, { error: { code: 'validacion', fields: { adultos: 'fuera_de_rango' } } })))
    await expect(api.crear({})).rejects.toMatchObject({ code: 'validacion', fields: { adultos: 'fuera_de_rango' } })
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }))
    await expect(api.lista()).rejects.toMatchObject({ status: 0, code: 'sin_conexion' })
  })
})
