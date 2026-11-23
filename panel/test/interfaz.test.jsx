import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Proveedor } from '../src/App.jsx'
import Detalle from '../src/pantallas/Detalle.jsx'
import Lista from '../src/pantallas/Lista.jsx'
import Dialogo from '../src/componentes/Dialogo.jsx'
import { fila } from './datos.js'

vi.mock('../src/api.js', async (original) => {
  const real = await original()
  return {
    ...real,
    api: Object.fromEntries(Object.keys(real.api).map((k) => [k, vi.fn()])),
  }
})
const { api } = await import('../src/api.js')

const MALICIOSO = '<img src=x onerror="window.__xss=1">Familia <b>Ficticia</b>'
const CONFIG = {
  ahora: '2026-11-20T12:00:00-06:00',
  cierre_plazo: '2027-01-31T00:00:00-06:00',
  fecha_limite_mostrar: '2027-01-30',
  congelamiento: '2027-02-06T00:00:00-06:00',
  cierre_planner: '2027-03-07T00:00:00-06:00',
}

function detalle(extra = {}) {
  return fila({
    nombre_mostrar: MALICIOSO,
    estado_respuesta: 'confirmada',
    confirmados: 2,
    mensaje: '<script>alert(1)</script> ¡Felicidades!',
    alergias: 'Nueces',
    telefono_principal: '+52' + '2025550123',
    contacto_alterno_tel: '+52' + '2025550199',
    enlace_activo: true,
    nota_interna: 'Nota <i>interna</i>',
    motivos_revision: [],
    recordatorios: 0,
    pases_planner_original: null,
    creada_en: '2026-11-20T10:00:00-06:00',
    actualizada_en: '2026-11-20T10:00:00-06:00',
    ...extra,
  })
}

let contenedor
let raiz
beforeEach(() => {
  contenedor = document.createElement('div')
  document.body.append(contenedor)
  raiz = createRoot(contenedor)
  window.__xss = undefined
  api.detalle.mockResolvedValue(detalle())
  api.historial.mockResolvedValue([
    { numero: 1, vigente: true, asiste: true, confirmados: 2, alergias: null, mensaje: '<b>hola</b>', origen: 'invitado', actor: null, creada_en: '2026-11-20T11:00:00-06:00' },
  ])
})
afterEach(() => {
  act(() => raiz.unmount())
  contenedor.remove()
  vi.clearAllMocks()
})

async function pintar(elemento, rol = 'admin') {
  const valor = { me: { correo: 'novia@ejemplo.invalid', rol }, config: CONFIG, reloj: () => new Date(CONFIG.ahora), esNovios: rol === 'admin' }
  await act(async () => {
    raiz.render(<Proveedor valor={valor}>{elemento}</Proveedor>)
  })
  await act(async () => {})
}

const botones = () => [...contenedor.querySelectorAll('button, a.boton')].map((b) => b.textContent.trim())
const titulos = () => [...contenedor.querySelectorAll('h2')].filter((h) => !h.closest('dialog')).map((h) => h.textContent)

describe('vista por rol (igual que la API, ADR 0026)', () => {
  it('novios: enlace, WhatsApp, escritura y recordatorios', async () => {
    await pintar(<Detalle codigo="INV-001" />, 'admin')
    expect(titulos()).toEqual(expect.arrayContaining(['Datos', 'Respuesta', 'Enlace personal', 'Recordatorios', 'Desbloqueo', 'Historial de respuestas']))
    expect(botones()).toEqual(expect.arrayContaining([
      'Editar', 'Archivar', 'Registrar respuesta', 'Ver enlace', 'WhatsApp al principal', 'WhatsApp al alterno',
      'Regenerar enlace', 'Revocar enlace', 'Recordatorio al principal', 'Recordatorio al alterno',
    ]))
  })

  it('planner: ve mensajes, historial y recordatorios; sin enlace ni botones de escritura', async () => {
    await pintar(<Detalle codigo="INV-001" />, 'lector')
    expect(titulos()).toEqual(['Datos', 'Respuesta', 'Recordatorios', 'Historial de respuestas'])
    expect(botones()).toEqual(['Recordatorio al principal', 'Recordatorio al alterno'])
    expect(contenedor.querySelector('dialog')).toBeNull()
    expect(contenedor.textContent).toContain('¡Felicidades!')
    expect(contenedor.textContent).not.toMatch(/enlace personal|ver enlace|whatsapp al/i)
    expect(api.verEnlace).not.toHaveBeenCalled()
    expect(api.whatsappEnlace).not.toHaveBeenCalled()
  })

  it('planner: sin «Nueva invitación» en la lista', async () => {
    api.lista.mockResolvedValue([fila()])
    await pintar(<Lista />, 'lector')
    expect(botones()).not.toContain('Nueva invitación')
    await pintar(<Lista />, 'admin')
    expect(botones()).toContain('Nueva invitación')
  })
})

describe('todo texto de usuario se pinta como texto', () => {
  it('en el detalle', async () => {
    await pintar(<Detalle codigo="INV-001" />)
    expect(contenedor.querySelector('h1').textContent).toBe(MALICIOSO)
    expect(contenedor.querySelector('img[src=x], b, i, script')).toBeNull()
    expect(contenedor.textContent).toContain('<script>alert(1)</script> ¡Felicidades!')
    expect(window.__xss).toBeUndefined()
  })

  it('en la lista (tarjetas y tabla)', async () => {
    api.lista.mockResolvedValue([fila({ nombre_mostrar: MALICIOSO })])
    await pintar(<Lista />)
    expect(contenedor.querySelector('.tarjeta-nombre').textContent).toBe(MALICIOSO)
    globalThis.__anchoPantalla = true
    await pintar(<Lista key="ancha" />)
    globalThis.__anchoPantalla = false
    expect(contenedor.querySelector('.tabla-lista a').textContent).toBe(MALICIOSO)
    expect(contenedor.querySelector('img[src=x], b')).toBeNull()
  })

  it('el mensaje de WhatsApp se muestra como texto y solo abre wa.me', async () => {
    api.whatsappEnlace.mockResolvedValue({ texto: 'Hola, <b>Familia</b>:\nhttps://ejemplo.invalid/#t=abc', telefono: '+52' + '2025550123', wa_url: 'javascript:alert(1)' })
    await pintar(<Detalle codigo="INV-001" />)
    const boton = [...contenedor.querySelectorAll('button')].find((b) => b.textContent === 'WhatsApp al principal')
    await act(async () => boton.click())
    expect(contenedor.querySelector('[data-testid=texto-whatsapp]').textContent).toContain('<b>Familia</b>')
    expect([...contenedor.querySelectorAll('a')].some((a) => a.textContent === 'Abrir en WhatsApp')).toBe(false)
    expect(api.enlaceEnviado).not.toHaveBeenCalled() // abrir no marca: lo decide quien envía
  })
})

describe('diálogo de confirmación', () => {
  it('se abre como modal y devuelve el foco al botón que lo abrió', async () => {
    const cerrar = vi.fn()
    const boton = document.createElement('button')
    document.body.append(boton)
    boton.focus()
    await pintar(<Dialogo abierto titulo="¿Archivar?" confirmar="Archivar" alConfirmar={() => {}} alCerrar={cerrar} />)
    const d = contenedor.querySelector('dialog')
    expect(d.hasAttribute('open')).toBe(true)
    expect(d.getAttribute('aria-labelledby')).toBe(d.querySelector('h2').id)
    await act(async () => [...d.querySelectorAll('button')].find((b) => b.textContent === 'Cancelar').click())
    expect(cerrar).toHaveBeenCalledTimes(1)
    expect(document.activeElement).toBe(boton)
    boton.remove()
  })
})
