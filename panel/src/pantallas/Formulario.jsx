// Crear (#/nueva) y editar (#/inv/INV-001/editar). Solo novios. La API valida todo; aquí solo
// se muestran sus errores por campo. Al editar se envían solo los campos cambiados.
import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { GRUPOS, LADOS, ROLES_BODA } from '../catalogos.js'
import { enlaces, ir } from '../rutas.js'
import { CAMPO, MOTIVO_CAMPO, textoError } from '../textos.js'
import { Campo, Cargando, MensajeError, Titulo } from '../componentes/comunes.jsx'

const TEXTO = ['nombre_mostrar', 'lado', 'grupo', 'nota_interna', 'telefono_principal', 'contacto_alterno_nombre', 'contacto_alterno_tel']
const NUMERO = ['adultos', 'ninos_autorizados', 'infantes', 'mesa', 'no_planner']
const OBLIGATORIOS_NUM = { adultos: 1, ninos_autorizados: 0, infantes: 0 }
const VACIO = {
  nombre_mostrar: '', adultos: '1', ninos_autorizados: '0', infantes: '0', lado: '', grupo: '',
  roles: [], mesa: '', nota_interna: '', no_planner: '', telefono_principal: '',
  contacto_alterno_nombre: '', contacto_alterno_tel: '',
}

function aFormulario(d) {
  const f = { ...VACIO, roles: [...d.roles] }
  for (const k of TEXTO) f[k] = d[k] ?? ''
  for (const k of NUMERO) f[k] = d[k] == null ? '' : String(d[k])
  return f
}

export function aDatos(f) {
  const datos = { roles: f.roles }
  for (const k of TEXTO) {
    const v = f[k].trim()
    datos[k] = v === '' ? null : v
  }
  for (const k of NUMERO) {
    const v = f[k].trim()
    datos[k] = v === '' ? null : /^-?\d+$/.test(v) ? Number(v) : v
  }
  return datos
}

// Campos obligatorios vacíos: se marcan sin llamar a la API (que respondería 400 genérico).
export function faltantes(datos) {
  const campos = {}
  for (const k of ['nombre_mostrar', ...Object.keys(OBLIGATORIOS_NUM)]) {
    if (datos[k] === null || datos[k] === undefined) campos[k] = 'obligatorio'
    else if (k !== 'nombre_mostrar' && typeof datos[k] !== 'number') campos[k] = 'fuera_de_rango'
  }
  return Object.keys(campos).length ? campos : null
}

export function cambios(original, datos) {
  const salida = {}
  for (const [k, v] of Object.entries(datos)) {
    const antes = original[k] ?? null
    if (JSON.stringify(antes) !== JSON.stringify(v)) salida[k] = v
  }
  return salida
}

export default function Formulario({ codigo }) {
  const nueva = !codigo
  const [original, setOriginal] = useState(null)
  const [f, setF] = useState(nueva ? VACIO : null)
  const [error, setError] = useState(null)
  const [ocupado, setOcupado] = useState(false)
  const formRef = useRef(null)

  useEffect(() => {
    if (nueva) return
    api.detalle(codigo).then(
      (d) => {
        setOriginal(d)
        setF(aFormulario(d))
      },
      setError,
    )
  }, [codigo, nueva])

  useEffect(() => {
    // Lleva el foco al primer campo con error.
    if (error?.code === 'validacion') formRef.current?.querySelector('[aria-invalid="true"]')?.focus()
  }, [error])

  if (!f) {
    return (
      <section>
        <p className="migas">
          <a href={enlaces.lista}>← Invitaciones</a>
        </p>
        {error ? <MensajeError>{textoError(error)}</MensajeError> : <Cargando />}
      </section>
    )
  }

  const cambiar = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const alternarRol = (rol) => (e) =>
    setF((x) => ({
      ...x,
      roles: e.target.checked ? ROLES_BODA.filter((r) => r === rol || x.roles.includes(r)) : x.roles.filter((r) => r !== rol),
    }))
  const err = (k) => {
    const m = error?.code === 'validacion' ? error.fields?.[k] : null
    return m ? MOTIVO_CAMPO[m] || MOTIVO_CAMPO.fuera_de_catalogo : null
  }
  const n = (v) => (/^\d+$/.test(v) ? Number(v) : 0)
  const pases = n(f.adultos) + n(f.ninos_autorizados)

  const guardar = async (e) => {
    e.preventDefault()
    setOcupado(true)
    setError(null)
    try {
      const datos = aDatos(f)
      const faltan = faltantes(datos)
      if (faltan) {
        setError({ code: 'validacion', fields: faltan })
        setOcupado(false)
        return
      }
      if (nueva) {
        const r = await api.crear(datos)
        ir(enlaces.detalle(r.codigo))
      } else {
        const delta = cambios(original, datos)
        if (Object.keys(delta).length) await api.editar(codigo, delta)
        ir(enlaces.detalle(codigo))
      }
    } catch (err2) {
      setError(err2)
      setOcupado(false)
    }
  }

  const volver = nueva ? enlaces.lista : enlaces.detalle(codigo)
  return (
    <section>
      <p className="migas">
        <a href={volver}>← {nueva ? 'Invitaciones' : 'Volver al detalle'}</a>
      </p>
      <Titulo sub={nueva ? null : codigo}>{nueva ? 'Nueva invitación' : 'Editar invitación'}</Titulo>
      <form ref={formRef} className="formulario" onSubmit={guardar} noValidate>
        <MensajeError>{error ? textoError(error) : null}</MensajeError>
        <fieldset>
          <legend>Invitación</legend>
          <Campo id="nombre_mostrar" etiqueta={CAMPO.nombre_mostrar} error={err('nombre_mostrar')}
            ayuda="Es el que verá el invitado: «Invitación para …».">
            {(p) => <input {...p} type="text" value={f.nombre_mostrar} onChange={cambiar('nombre_mostrar')} required autoComplete="off" />}
          </Campo>
          <div className="fila-campos">
            {['adultos', 'ninos_autorizados', 'infantes'].map((k) => (
              <Campo key={k} id={k} etiqueta={CAMPO[k]} error={err(k)}>
                {(p) => <input {...p} type="number" inputMode="numeric" min={k === 'adultos' ? 1 : 0} value={f[k]} onChange={cambiar(k)} required />}
              </Campo>
            ))}
          </div>
          <p className="pases" aria-live="polite">
            Pases: <strong>{pases}</strong> <span className="tenue">(adultos + niños; los infantes no cuentan)</span>
          </p>
        </fieldset>
        <fieldset>
          <legend>Organización</legend>
          <div className="fila-campos">
            <Campo id="lado" etiqueta={CAMPO.lado} error={err('lado')} opcional>
              {(p) => (
                <select {...p} value={f.lado} onChange={cambiar('lado')}>
                  <option value="">Sin lado</option>
                  {LADOS.map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
              )}
            </Campo>
            <Campo id="grupo" etiqueta={CAMPO.grupo} error={err('grupo')} opcional>
              {(p) => (
                <select {...p} value={f.grupo} onChange={cambiar('grupo')}>
                  <option value="">Sin grupo</option>
                  {GRUPOS.map((g) => <option key={g} value={g}>{g}</option>)}
                </select>
              )}
            </Campo>
            <Campo id="mesa" etiqueta={CAMPO.mesa} error={err('mesa')} opcional>
              {(p) => <input {...p} type="number" inputMode="numeric" min="1" value={f.mesa} onChange={cambiar('mesa')} />}
            </Campo>
            <Campo id="no_planner" etiqueta={CAMPO.no_planner} error={err('no_planner')} opcional>
              {(p) => <input {...p} type="number" inputMode="numeric" min="1" value={f.no_planner} onChange={cambiar('no_planner')} />}
            </Campo>
          </div>
          <fieldset className="roles" aria-describedby={err('roles') ? 'roles-error' : undefined}>
            <legend>{CAMPO.roles} <span className="opcional">(opcional)</span></legend>
            <div className="roles-rejilla">
              {ROLES_BODA.map((rol, i) => (
                <label key={rol} htmlFor={`rol-${i}`}>
                  <input id={`rol-${i}`} type="checkbox" checked={f.roles.includes(rol)} onChange={alternarRol(rol)} /> {rol}
                </label>
              ))}
            </div>
            {err('roles') ? <p className="error-campo" id="roles-error"><span aria-hidden="true">⚠ </span>{err('roles')}</p> : null}
          </fieldset>
          <Campo id="nota_interna" etiqueta={CAMPO.nota_interna} error={err('nota_interna')} opcional
            ayuda="No la ve el invitado. La ven los novios y la planner.">
            {(p) => <textarea {...p} rows="3" value={f.nota_interna} onChange={cambiar('nota_interna')} />}
          </Campo>
        </fieldset>
        <fieldset>
          <legend>Contacto (para WhatsApp)</legend>
          <Campo id="telefono_principal" etiqueta={CAMPO.telefono_principal} error={err('telefono_principal')} opcional
            ayuda="10 dígitos, o con lada internacional (+…).">
            {(p) => <input {...p} type="tel" inputMode="tel" autoComplete="off" value={f.telefono_principal} onChange={cambiar('telefono_principal')} />}
          </Campo>
          <div className="fila-campos">
            <Campo id="contacto_alterno_nombre" etiqueta={CAMPO.contacto_alterno_nombre} error={err('contacto_alterno_nombre')} opcional>
              {(p) => <input {...p} type="text" autoComplete="off" value={f.contacto_alterno_nombre} onChange={cambiar('contacto_alterno_nombre')} />}
            </Campo>
            <Campo id="contacto_alterno_tel" etiqueta={CAMPO.contacto_alterno_tel} error={err('contacto_alterno_tel')} opcional>
              {(p) => <input {...p} type="tel" inputMode="tel" autoComplete="off" value={f.contacto_alterno_tel} onChange={cambiar('contacto_alterno_tel')} />}
            </Campo>
          </div>
        </fieldset>
        <div className="acciones">
          <button type="submit" className="boton" disabled={ocupado}>
            {nueva ? 'Crear invitación' : 'Guardar cambios'}
          </button>
          <a className="boton secundario" href={volver}>
            Cancelar
          </a>
        </div>
      </form>
    </section>
  )
}
