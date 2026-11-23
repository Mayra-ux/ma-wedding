// Importar el Excel/CSV de la planner (ADR 0028). Solo novios.
// Vista previa (no guarda nada) → elegir hoja si hace falta → aplicar (todo o nada).
import { useState } from 'react'
import { api } from '../api.js'
import { LADOS, MAX_IMPORTACION } from '../catalogos.js'
import { ACCION_FILA, CAMPO, ERROR_FILA, MOTIVO_REVISION, textoError } from '../textos.js'
import { Campo, MensajeError, MensajeOk, Nota, Titulo } from '../componentes/comunes.jsx'
import { useAncho } from './Lista.jsx'

const TIPOS = {
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  csv: 'text/csv',
}

export function tipoDeArchivo(nombre) {
  const ext = (nombre || '').toLowerCase().split('.').pop()
  return TIPOS[ext] || null
}

export default function Importar() {
  const [archivo, setArchivo] = useState(null) // { nombre, datos, tipo }
  const [lado, setLado] = useState('')
  const [hojas, setHojas] = useState(null)
  const [hoja, setHoja] = useState('')
  const [vista, setVista] = useState(null)
  const [aplicado, setAplicado] = useState(null)
  const [error, setError] = useState(null)
  const [ocupado, setOcupado] = useState(false)

  const reiniciar = () => {
    setHojas(null)
    setHoja('')
    setVista(null)
    setAplicado(null)
    setError(null)
  }

  const elegir = async (e) => {
    reiniciar()
    const f = e.target.files?.[0]
    setArchivo(null)
    if (!f) return
    const tipo = tipoDeArchivo(f.name)
    if (!tipo) return setError({ code: 'formato_no_soportado' })
    if (f.size > MAX_IMPORTACION) return setError({ code: 'cuerpo_demasiado_grande' })
    setArchivo({ nombre: f.name, datos: await f.arrayBuffer(), tipo })
  }

  const previsualizar = async (e) => {
    e.preventDefault()
    if (!archivo) return
    setOcupado(true)
    setError(null)
    setVista(null)
    setAplicado(null)
    try {
      setVista(await api.vistaPrevia(archivo.datos, archivo.tipo, hoja || null, lado || null))
    } catch (err) {
      if (err.code === 'hoja_requerida' && Array.isArray(err.fields?.hojas)) {
        setHojas(err.fields.hojas)
        setHoja('')
      }
      setError(err)
    } finally {
      setOcupado(false)
    }
  }

  const aplicar = async () => {
    setOcupado(true)
    setError(null)
    try {
      const r = await api.aplicar(archivo.datos, archivo.tipo, hoja || null, lado || null)
      setAplicado(r)
      setVista(null)
    } catch (err) {
      setError(err)
    } finally {
      setOcupado(false)
    }
  }

  const conErrores = vista?.resumen.errores > 0
  return (
    <section>
      <Titulo>Importar lista</Titulo>
      <Nota>
        Acepta el Excel (.xlsx) o un CSV de la planner, de hasta 2 MB. La vista previa no guarda nada. Cada hoja de la
        planner se importa <strong>una sola vez</strong>; después, haz los cambios en el panel o reimporta el archivo
        exportado (que trae Código INV).
      </Nota>
      <form className="formulario" onSubmit={previsualizar} noValidate>
        <Campo id="archivo" etiqueta="Archivo">
          {(p) => <input {...p} type="file" accept=".xlsx,.csv" onChange={elegir} />}
        </Campo>
        <Campo id="lado" etiqueta={CAMPO.lado_por_defecto} opcional
          ayuda="Se usa solo en las filas con «Invitado de» vacío (normalmente, el lado de la hoja).">
          {(p) => (
            <select {...p} value={lado} onChange={(e) => { setLado(e.target.value); setVista(null) }}>
              <option value="">Ninguno</option>
              {LADOS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          )}
        </Campo>
        {hojas ? (
          <fieldset className="opciones">
            <legend>Hoja de invitados</legend>
            {hojas.map((h, i) => (
              <label key={h} htmlFor={`hoja-${i}`}>
                <input id={`hoja-${i}`} type="radio" name="hoja" value={h} checked={hoja === h}
                  onChange={() => { setHoja(h); setVista(null) }} /> {h}
              </label>
            ))}
          </fieldset>
        ) : null}
        <MensajeError>{error && !(error.code === 'hoja_requerida' && hoja) ? textoError(error) : null}</MensajeError>
        <div className="acciones">
          <button type="submit" className="boton" disabled={!archivo || ocupado || (hojas && !hoja)}>
            Ver vista previa
          </button>
        </div>
      </form>

      {vista ? (
        <section className="panel" aria-labelledby="t-vista">
          <h2 id="t-vista">Vista previa{vista.hoja ? ` · ${vista.hoja}` : ''}</h2>
          <ResumenImportacion r={vista.resumen} />
          {vista.resumen.advertencia ? (
            <div className="advertencia" role="note">
              <span aria-hidden="true">⚠ </span>
              {vista.resumen.advertencia}
            </div>
          ) : null}
          {vista.columnas_desconocidas?.length ? (
            <Nota>Columnas que no se leen: {vista.columnas_desconocidas.join(', ')}.</Nota>
          ) : null}
          {vista.no_incluidas?.length ? (
            <Nota>Invitaciones del sistema que no vienen en el archivo (no se tocan): {vista.no_incluidas.join(', ')}.</Nota>
          ) : null}
          <Filas filas={vista.filas} />
          {conErrores ? (
            <MensajeError>Corrige las filas con error en el archivo y vuelve a cargarlo: con errores no se aplica nada.</MensajeError>
          ) : null}
          <div className="acciones">
            <button type="button" className="boton" onClick={aplicar} disabled={ocupado || conErrores}>
              Aplicar importación
            </button>
          </div>
        </section>
      ) : null}

      {aplicado ? (
        <section className="panel" aria-labelledby="t-aplicado">
          <h2 id="t-aplicado">Importación aplicada</h2>
          <MensajeOk>
            {aplicado.resumen.altas} nuevas, {aplicado.resumen.actualizaciones} actualizadas y {aplicado.resumen.sin_cambios} sin
            cambios.
          </MensajeOk>
          <ResumenImportacion r={aplicado.resumen} />
        </section>
      ) : null}
    </section>
  )
}

function ResumenImportacion({ r }) {
  const cifras = [
    ['Filas', r.filas],
    ['Nuevas', r.altas],
    ['Actualizaciones', r.actualizaciones],
    ['Sin cambios', r.sin_cambios],
    ['Con error', r.errores],
    ['En revisión', r.en_revision],
    ['Avisos', r.avisos],
  ]
  return (
    <dl className="cifras cifras-chicas">
      {cifras.map(([t, n]) => (
        <div key={t} className="cifra">
          <dt>{t}</dt>
          <dd>{n}</dd>
        </div>
      ))}
    </dl>
  )
}

function Detalles({ fila }) {
  const lineas = [
    ...fila.errores.map((e) => ['error', `⚠ ${ERROR_FILA[e] || e}`]),
    ...fila.motivos_revision.map((m) => ['revision', `⚑ ${MOTIVO_REVISION[m] || m}`]),
    ...fila.avisos.map((a) => ['aviso', a.mensaje]),
  ]
  const campos = Object.keys(fila.cambios || {})
  if (fila.accion === 'actualizacion' && campos.length) {
    lineas.push(['cambio', `Cambia: ${campos.map((c) => CAMPO[c] || c).join(', ')}`])
  }
  if (!lineas.length) return <span className="tenue">—</span>
  return (
    <ul className="detalles-fila">
      {lineas.map(([k, t], i) => (
        <li key={i} className={`detalle-${k}`}>
          {t}
        </li>
      ))}
    </ul>
  )
}

function Filas({ filas }) {
  const ancho = useAncho()
  if (!ancho) {
    return (
      <ul className="tarjetas">
        {filas.map((f) => (
          <li key={f.fila} className={`tarjeta tarjeta-${f.accion}`}>
            <p className="tarjeta-linea">
              <strong>{f.nombre || 'Sin nombre'}</strong>
              <span className="etiqueta">{ACCION_FILA[f.accion]}</span>
            </p>
            <p className="tenue">Fila {f.fila}{f.codigo ? ` · ${f.codigo}` : ''}</p>
            <Detalles fila={f} />
          </li>
        ))}
      </ul>
    )
  }
  return (
    <table className="tabla">
      <caption className="solo-lector">Resultado por fila</caption>
      <thead>
        <tr>
          <th scope="col">Fila</th>
          <th scope="col">Código</th>
          <th scope="col">Nombre</th>
          <th scope="col">Resultado</th>
          <th scope="col">Detalles</th>
        </tr>
      </thead>
      <tbody>
        {filas.map((f) => (
          <tr key={f.fila} className={`fila-${f.accion}`}>
            <td className="numero">{f.fila}</td>
            <td className="codigo">{f.codigo || '—'}</td>
            <td>{f.nombre || '—'}</td>
            <td>{ACCION_FILA[f.accion]}</td>
            <td>
              <Detalles fila={f} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
