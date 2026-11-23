// Exportar la lista (ADR 0026, 0028). Novios y planner, mismas 19 columnas.
import { useState } from 'react'
import { api } from '../api.js'
import { textoError } from '../textos.js'
import { MensajeError, MensajeOk, Nota, Titulo } from '../componentes/comunes.jsx'

export function nombreDescarga(disposicion, respaldo) {
  const m = /filename="([^"]+)"/.exec(disposicion || '')
  return m ? m[1] : respaldo
}

export default function Exportar() {
  const [formato, setFormato] = useState('xlsx')
  const [solo, setSolo] = useState(false)
  const [error, setError] = useState(null)
  const [ok, setOk] = useState(null)
  const [ocupado, setOcupado] = useState(false)

  const descargar = async (e) => {
    e.preventDefault()
    setOcupado(true)
    setError(null)
    setOk(null)
    try {
      const r = await api.exportar(formato, solo)
      const nombre = nombreDescarga(r.headers.get('content-disposition'), `invitados.${formato}`)
      const url = URL.createObjectURL(await r.blob())
      const a = document.createElement('a')
      a.href = url
      a.download = nombre
      document.body.append(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 10_000)
      setOk(`Se descargó ${nombre}.`)
    } catch (err) {
      setError(err)
    } finally {
      setOcupado(false)
    }
  }

  return (
    <section>
      <Titulo>Exportar lista</Titulo>
      <Nota>
        19 columnas: Código INV, las de la planner y Mensaje del invitado, Grupo, Rol y Alergias. Sin invitaciones
        archivadas y sin enlaces.
      </Nota>
      <form className="formulario" onSubmit={descargar}>
        <fieldset className="opciones">
          <legend>Formato</legend>
          <label htmlFor="fmt-xlsx">
            <input id="fmt-xlsx" type="radio" name="formato" value="xlsx" checked={formato === 'xlsx'} onChange={() => setFormato('xlsx')} /> Excel (.xlsx)
          </label>
          <label htmlFor="fmt-csv">
            <input id="fmt-csv" type="radio" name="formato" value="csv" checked={formato === 'csv'} onChange={() => setFormato('csv')} /> CSV
          </label>
        </fieldset>
        <div className="campo campo-casilla">
          <input id="solo-confirmados" type="checkbox" checked={solo} onChange={(e) => setSolo(e.target.checked)} />
          <label htmlFor="solo-confirmados">Solo confirmados</label>
        </div>
        <div className="advertencia" role="note">
          <span aria-hidden="true">⚠ </span>
          El archivo contiene teléfonos y alergias: guárdalo fuera del repositorio y bórralo o recórtalo el 5 de abril de 2027.
        </div>
        <MensajeError>{error ? textoError(error) : null}</MensajeError>
        <div aria-live="polite">
          <MensajeOk>{ok}</MensajeOk>
        </div>
        <div className="acciones">
          <button type="submit" className="boton" disabled={ocupado}>
            Descargar
          </button>
        </div>
      </form>
    </section>
  )
}
