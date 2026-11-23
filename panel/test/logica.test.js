import { afterEach, describe, expect, it, vi } from 'vitest'
import { urlWhatsappSegura } from '../src/api.js'
import { fases, relojDelServidor } from '../src/fases.js'
import { FILTROS_INICIALES, calcularResumen, filtrar, hayFiltros, normalizar } from '../src/filtros.js'
import { diaLocal, finDelDia, telefono } from '../src/formato.js'
import { vigilarInactividad, INACTIVIDAD_MS } from '../src/inactividad.js'
import { leerRuta } from '../src/rutas.js'
import { textoError } from '../src/textos.js'
import { aDatos, cambios, faltantes } from '../src/pantallas/Formulario.jsx'
import { tipoDeArchivo } from '../src/pantallas/Importar.jsx'
import { nombreDescarga } from '../src/pantallas/Exportar.jsx'
import { fila } from './datos.js'


describe('búsqueda y filtros', () => {
  const filas = [
    fila({ codigo: 'INV-001', nombre_mostrar: 'Familia Pérez Núñez', lado: 'Novia', grupo: 'Familia', roles: ['Paje'],
      estado_respuesta: 'confirmada', confirmados: 2, enlace_activo: true, enlace_enviado: true, no_planner: 14 }),
    fila({ codigo: 'INV-002', nombre_mostrar: 'Amigos del Trabajo', lado: 'Novio', grupo: 'Trabajo',
      estado_respuesta: 'no_asiste', confirmados: 0, requiere_revision: true, enlace_activo: true }),
    fila({ codigo: 'INV-003', nombre_mostrar: 'Familia Archivada', archivada: true }),
  ]

  it('normaliza acentos, mayúsculas y espacios', () => {
    expect(normalizar('  Familia   PÉREZ  Núñez ')).toBe('familia perez nunez')
  })

  it('busca sin acentos por nombre, código y No.', () => {
    const q = (texto) => filtrar(filas, { ...FILTROS_INICIALES, texto }).map((f) => f.codigo)
    expect(q('perez nunez')).toEqual(['INV-001'])
    expect(q('inv-002')).toEqual(['INV-002'])
    expect(q('14')).toEqual(['INV-001'])
    expect(q('familia')).toEqual(['INV-001']) // sin archivadas
  })

  it('filtra por estado, lado, rol, revisión, enlace y archivadas', () => {
    const q = (f) => filtrar(filas, { ...FILTROS_INICIALES, ...f }).map((x) => x.codigo)
    expect(q({ estado: 'no_asiste' })).toEqual(['INV-002'])
    expect(q({ lado: 'Novia' })).toEqual(['INV-001'])
    expect(q({ lado: 'sin_lado', archivadas: true })).toEqual(['INV-003'])
    expect(q({ rol: 'Paje' })).toEqual(['INV-001'])
    expect(q({ revision: 'si' })).toEqual(['INV-002'])
    expect(q({ enlace: 'enviado' })).toEqual(['INV-001'])
    expect(q({ enlace: 'no_enviado' })).toEqual(['INV-002'])
    expect(q({ enlace: 'sin_enlace', archivadas: true })).toEqual(['INV-003'])
    expect(q({ archivadas: true })).toHaveLength(3)
    expect(hayFiltros(FILTROS_INICIALES)).toBe(false)
    expect(hayFiltros({ ...FILTROS_INICIALES, rol: 'Paje' })).toBe(true)
  })

  it('el resumen replica al de la API (archivadas fuera; una invitación cuenta en cada rol)', () => {
    const r = calcularResumen([
      ...filas,
      fila({ codigo: 'INV-004', adultos: 3, ninos_autorizados: 1, infantes: 1, pases: 4, roles: ['Paje', 'Ofrendas'],
        estado_respuesta: 'confirmada', confirmados: 4, grupo: 'Familia' }),
    ])
    expect(r.invitaciones).toBe(3)
    expect(r.pases_asignados).toBe(8)
    expect(r.personas_confirmadas).toBe(6)
    expect(r.ninos_autorizados).toBe(1)
    expect(r.infantes).toBe(1)
    expect(r.por_estado.confirmada).toEqual({ invitaciones: 2, pases: 6, confirmados: 6 })
    expect(r.por_estado.no_asiste).toEqual({ invitaciones: 1, pases: 2, confirmados: 0 })
    expect(r.por_rol.Paje).toEqual({ invitaciones: 2, pases: 6, confirmados: 6 })
    expect(r.por_lado.sin_lado.invitaciones).toBe(1)
    expect(r.por_grupo.Familia.invitaciones).toBe(2)
    expect(Object.keys(r.por_rol)).toHaveLength(13)
  })
})

describe('enrutado por hash', () => {
  it.each([
    ['', { nombre: 'lista' }],
    ['#/', { nombre: 'lista' }],
    ['#/inv/INV-001', { nombre: 'detalle', codigo: 'INV-001' }],
    ['#/inv/INV-1234/editar', { nombre: 'editar', codigo: 'INV-1234' }],
    ['#/nueva', { nombre: 'nueva' }],
    ['#/importar', { nombre: 'importar' }],
    ['#/exportar', { nombre: 'exportar' }],
    ['#/actividad', { nombre: 'actividad' }],
    ['#/inv/1', { nombre: 'no_encontrada' }],
    ['#/inv/INV-001/borrar', { nombre: 'no_encontrada' }],
    ['#/inv/<script>', { nombre: 'no_encontrada' }],
    ['#/otra', { nombre: 'no_encontrada' }],
  ])('%s', (hash, esperado) => {
    expect(leerRuta(hash)).toEqual(esperado)
  })
})

describe('fases con la hora del servidor', () => {
  const config = {
    ahora: '2027-01-31T00:00:00-06:00',
    cierre_plazo: '2027-01-31T00:00:00-06:00',
    congelamiento: '2027-02-06T00:00:00-06:00',
    cierre_planner: '2027-03-07T00:00:00-06:00',
  }
  const en = (iso) => fases(config, new Date(iso))

  it('plazo, desbloqueo, congelamiento y recordatorios', () => {
    expect(en('2027-01-30T23:59:59-06:00')).toMatchObject({ plazoAbierto: true, puedeDesbloquear: false, tipoRecordatorio: 'confirmar' })
    expect(en('2027-01-31T00:00:00-06:00')).toMatchObject({ plazoAbierto: false, puedeDesbloquear: true, tipoRecordatorio: 'evento' })
    expect(en('2027-02-06T00:00:00-06:00')).toMatchObject({ puedeDesbloquear: false, congelada: true, tipoRecordatorio: 'evento' })
    expect(en('2027-03-06T23:59:59-06:00')).toMatchObject({ recordatoriosCerrados: false })
    expect(en('2027-03-07T00:00:00-06:00')).toMatchObject({ recordatoriosCerrados: true, tipoRecordatorio: null })
  })

  it('el reloj sigue la hora del servidor aunque el equipo tenga otra', () => {
    const local = Date.parse('2026-11-20T12:00:00Z')
    vi.spyOn(Date, 'now').mockReturnValue(local + 5000)
    const reloj = relojDelServidor(config, local)
    expect(reloj().toISOString()).toBe('2027-01-31T06:00:05.000Z')
    vi.restoreAllMocks()
  })
})

describe('formatos', () => {
  it('fin del día elegido = 00:00 (−06:00) del día siguiente', () => {
    expect(finDelDia('2027-02-05')).toBe('2027-02-06T06:00:00.000Z')
    expect(diaLocal(new Date('2027-02-06T05:59:59Z'))).toBe('2027-02-05')
  })
  it('teléfono legible', () => {
    expect(telefono('+52' + '2025550123')).toBe('+52 ' + '202 555 0123') // por partes (test_sin_telefonos_reales)
    expect(telefono('+12025550199')).toBe('+12025550199')
  })
})

describe('cierre por inactividad (30 min)', () => {
  afterEach(() => vi.useRealTimers())

  it('vence a los 30 min sin interacción y una interacción reinicia la cuenta', () => {
    vi.useFakeTimers()
    let t = 0
    const vencer = vi.fn()
    const parar = vigilarInactividad(vencer, INACTIVIDAD_MS, () => t)
    t = INACTIVIDAD_MS - 1000
    window.dispatchEvent(new KeyboardEvent('keydown'))
    t += INACTIVIDAD_MS - 1000
    vi.advanceTimersByTime(30_000)
    expect(vencer).not.toHaveBeenCalled()
    t += 1000
    vi.advanceTimersByTime(30_000)
    expect(vencer).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(60_000)
    expect(vencer).toHaveBeenCalledTimes(1)
    parar()
    expect(INACTIVIDAD_MS).toBe(30 * 60 * 1000)
  })

  it('al volver a la pestaña (celular dormido) revisa de inmediato', () => {
    let t = 0
    const vencer = vi.fn()
    const parar = vigilarInactividad(vencer, INACTIVIDAD_MS, () => t)
    t = INACTIVIDAD_MS + 1
    document.dispatchEvent(new Event('visibilitychange'))
    expect(vencer).toHaveBeenCalledTimes(1)
    parar()
  })
})

describe('utilidades de pantallas', () => {
  it('solo abre URLs https://wa.me/', () => {
    expect(urlWhatsappSegura('https://wa.me/522025550123?text=Hola')).toBeTruthy()
    for (const mala of ['javascript:alert(1)', 'https://wa.me.evil.example/', 'http://wa.me/1', null, 3]) {
      expect(urlWhatsappSegura(mala)).toBeNull()
    }
  })

  it('tipo de archivo por extensión y nombre de descarga', () => {
    expect(tipoDeArchivo('Lista.XLSX')).toContain('spreadsheetml')
    expect(tipoDeArchivo('lista.csv')).toBe('text/csv')
    expect(tipoDeArchivo('lista.xls')).toBeNull()
    expect(tipoDeArchivo('lista.xlsm')).toBeNull()
    expect(nombreDescarga('attachment; filename="invitados-2026-11-20.xlsx"', 'x')).toBe('invitados-2026-11-20.xlsx')
    expect(nombreDescarga(null, 'respaldo.csv')).toBe('respaldo.csv')
  })

  it('formulario: tipos, obligatorios y solo los campos cambiados', () => {
    const datos = aDatos({
      nombre_mostrar: ' Familia Ficticia ', adultos: '2', ninos_autorizados: '0', infantes: '', lado: 'Novia',
      grupo: '', roles: ['Paje'], mesa: '', nota_interna: '', no_planner: '7', telefono_principal: '',
      contacto_alterno_nombre: '', contacto_alterno_tel: '',
    })
    expect(datos).toMatchObject({ nombre_mostrar: 'Familia Ficticia', adultos: 2, infantes: null, lado: 'Novia', grupo: null, mesa: null, no_planner: 7 })
    expect(faltantes(datos)).toEqual({ infantes: 'obligatorio' })
    const original = { ...datos, infantes: 0, lado: 'Novio', roles: ['Paje'] }
    expect(cambios(original, { ...datos, infantes: 0 })).toEqual({ lado: 'Novia' })
  })

  it('mensaje de error desconocido cae en el genérico', () => {
    expect(textoError({ code: 'no_existe' })).toBe('Ocurrió un error. Inténtalo de nuevo.')
    expect(textoError({ code: 'sin_permiso' })).toBe('Tu cuenta no tiene permiso para esta acción.')
  })
})
