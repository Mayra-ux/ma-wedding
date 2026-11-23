import { useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import { usePanel } from '../App.jsx'
import { api } from '../api.js'
import { ESTADOS, GRUPOS, LADOS, ROLES_BODA } from '../catalogos.js'
import { FILTROS_INICIALES, calcularResumen, filtrar, hayFiltros } from '../filtros.js'
import { enlaces } from '../rutas.js'
import { ESTADO, textoError } from '../textos.js'
import { Cargando, Estado, MensajeError, Titulo } from '../componentes/comunes.jsx'

const ANCHO = '(min-width: 64rem)'

export function useAncho() {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia(ANCHO)
      m.addEventListener('change', cb)
      return () => m.removeEventListener('change', cb)
    },
    () => window.matchMedia(ANCHO).matches,
  )
}

export default function Lista() {
  const { esNovios } = usePanel()
  const [filas, setFilas] = useState(null)
  const [error, setError] = useState(null)
  const [f, setF] = useState(FILTROS_INICIALES)
  const ancho = useAncho()

  useEffect(() => {
    let vivo = true
    api.lista().then(
      (d) => vivo && setFilas(d),
      (e) => vivo && setError(e),
    )
    return () => {
      vivo = false
    }
  }, [])

  const visibles = useMemo(() => (filas ? filtrar(filas, f) : []), [filas, f])
  const total = useMemo(() => (filas ? calcularResumen(filas) : null), [filas])
  const filtrado = useMemo(() => calcularResumen(visibles), [visibles])
  const cambiar = (campo) => (e) =>
    setF((x) => ({ ...x, [campo]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  return (
    <section>
      <Titulo>Invitaciones</Titulo>
      {esNovios ? (
        <p className="acciones-pantalla">
          <a className="boton" href={enlaces.nueva}>
            Nueva invitación
          </a>
        </p>
      ) : null}
      <MensajeError>{error ? textoError(error) : null}</MensajeError>
      {!filas && !error ? <Cargando /> : null}
      {total ? <Resumen r={total} /> : null}
      {filas ? (
        <>
          <div className="busqueda">
            <label htmlFor="buscar">Buscar por nombre, código o No.</label>
            <input id="buscar" type="search" value={f.texto} onChange={cambiar('texto')} autoComplete="off" />
          </div>
          <details className="filtros" open={ancho}>
            <summary>Filtros{hayFiltros({ ...f, texto: '' }) ? ' (activos)' : ''}</summary>
            <div className="filtros-rejilla">
              <Selector id="f-estado" etiqueta="Estado" valor={f.estado} alCambiar={cambiar('estado')}
                opciones={ESTADOS.map((e) => [e, ESTADO[e].texto])} />
              <Selector id="f-lado" etiqueta="Invitado de" valor={f.lado} alCambiar={cambiar('lado')}
                opciones={[...LADOS.map((l) => [l, l]), ['sin_lado', 'Sin lado']]} />
              <Selector id="f-grupo" etiqueta="Grupo" valor={f.grupo} alCambiar={cambiar('grupo')}
                opciones={[...GRUPOS.map((g) => [g, g]), ['sin_grupo', 'Sin grupo']]} />
              <Selector id="f-rol" etiqueta="Rol" valor={f.rol} alCambiar={cambiar('rol')}
                opciones={ROLES_BODA.map((r) => [r, r])} />
              <Selector id="f-revision" etiqueta="Revisión" valor={f.revision} alCambiar={cambiar('revision')}
                opciones={[['si', 'En revisión'], ['no', 'Sin revisión']]} />
              <Selector id="f-enlace" etiqueta="Enlace" valor={f.enlace} alCambiar={cambiar('enlace')}
                opciones={[['enviado', 'Enviado'], ['no_enviado', 'Activo sin enviar'], ['sin_enlace', 'Sin enlace']]} />
              <div className="campo campo-casilla">
                <input id="f-archivadas" type="checkbox" checked={f.archivadas} onChange={cambiar('archivadas')} />
                <label htmlFor="f-archivadas">Mostrar archivadas</label>
              </div>
              <button type="button" className="boton secundario" onClick={() => setF(FILTROS_INICIALES)}
                disabled={!hayFiltros(f)}>
                Limpiar filtros
              </button>
            </div>
          </details>
          <p className="conteo" role="status" aria-live="polite">
            {hayFiltros(f)
              ? `Mostrando ${visibles.length} de ${filas.length} · ${filtrado.pases_asignados} pases · ${filtrado.personas_confirmadas} confirmados`
              : `${visibles.length} invitaciones`}
          </p>
          {visibles.length === 0 ? (
            <p>No hay invitaciones con estos filtros.</p>
          ) : ancho ? (
            <Tabla filas={visibles} />
          ) : (
            <Tarjetas filas={visibles} />
          )}
        </>
      ) : null}
    </section>
  )
}

function Selector({ id, etiqueta, valor, alCambiar, opciones }) {
  return (
    <div className="campo">
      <label htmlFor={id}>{etiqueta}</label>
      <select id={id} value={valor} onChange={alCambiar}>
        <option value="">Todos</option>
        {opciones.map(([v, t]) => (
          <option key={v} value={v}>
            {t}
          </option>
        ))}
      </select>
    </div>
  )
}

function Resumen({ r }) {
  const cifras = [
    ['Invitaciones', r.invitaciones, 'resumen-invitaciones'],
    ['Pases asignados', r.pases_asignados, 'resumen-pases'],
    ['Personas confirmadas', r.personas_confirmadas, 'resumen-confirmados'],
    ['Pendientes', r.por_estado.pendiente.invitaciones, 'resumen-pendientes'],
    ['No asisten', r.por_estado.no_asiste.invitaciones, 'resumen-no-asisten'],
    ['Niños autorizados', r.ninos_autorizados, 'resumen-ninos'],
    ['Infantes', r.infantes, 'resumen-infantes'],
  ]
  return (
    <section className="resumen" aria-labelledby="titulo-resumen">
      <h2 id="titulo-resumen" className="solo-lector">
        Resumen
      </h2>
      <dl className="cifras">
        {cifras.map(([t, n, id]) => (
          <div key={t} className="cifra" data-testid={id}>
            <dt>{t}</dt>
            <dd>{n}</dd>
          </div>
        ))}
      </dl>
      <details className="desglose">
        <summary>Ver por estado, lado, grupo y rol</summary>
        <Desglose titulo="Por estado" cubos={r.por_estado} etiqueta={(k) => ESTADO[k].texto} />
        <Desglose titulo="Por lado" cubos={r.por_lado} etiqueta={(k) => (k === 'sin_lado' ? 'Sin lado' : k)} />
        <Desglose titulo="Por grupo" cubos={r.por_grupo} etiqueta={(k) => (k === 'sin_grupo' ? 'Sin grupo' : k)} />
        <Desglose titulo="Por rol" cubos={r.por_rol} etiqueta={(k) => k} />
      </details>
    </section>
  )
}

function Desglose({ titulo, cubos, etiqueta }) {
  return (
    <table className="tabla tabla-desglose">
      <caption>{titulo}</caption>
      <thead>
        <tr>
          <th scope="col">&nbsp;</th>
          <th scope="col">Invitaciones</th>
          <th scope="col">Pases</th>
          <th scope="col">Confirmados</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(cubos).map(([k, c]) => (
          <tr key={k}>
            <th scope="row">{etiqueta(k)}</th>
            <td>{c.invitaciones}</td>
            <td>{c.pases}</td>
            <td>{c.confirmados}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Marcas({ fila }) {
  const m = []
  if (fila.archivada) m.push(['archivada', 'Archivada'])
  if (fila.requiere_revision) m.push(['revision', '⚑ En revisión'])
  if (fila.enlace_enviado) m.push(['enviado', 'Enlace enviado'])
  else if (fila.enlace_activo) m.push(['activo', 'Enlace sin enviar'])
  if (fila.recordatorios) m.push(['recordatorios', `${fila.recordatorios} recordatorio${fila.recordatorios > 1 ? 's' : ''}`])
  if (m.length === 0) return null
  return (
    <ul className="marcas">
      {m.map(([k, t]) => (
        <li key={k} className={`marca-${k}`}>
          {t}
        </li>
      ))}
    </ul>
  )
}

function lugares(fila) {
  return fila.estado_respuesta === 'pendiente' ? `${fila.pases} pases` : `${fila.confirmados} de ${fila.pases}`
}

function Tarjetas({ filas }) {
  return (
    <ul className="tarjetas">
      {filas.map((fila) => (
        <li key={fila.codigo} className={`tarjeta${fila.archivada ? ' tarjeta-archivada' : ''}`}>
          <a className="tarjeta-enlace" href={enlaces.detalle(fila.codigo)}>
            <span className="tarjeta-nombre">{fila.nombre_mostrar}</span>
            <span className="codigo">{fila.codigo}</span>
          </a>
          <div className="tarjeta-linea">
            <Estado estado={fila.estado_respuesta} />
            <span>{lugares(fila)}</span>
          </div>
          <div className="tarjeta-linea tenue">
            <span>{[fila.lado, fila.grupo].filter(Boolean).join(' · ') || 'Sin lado ni grupo'}</span>
          </div>
          <Marcas fila={fila} />
        </li>
      ))}
    </ul>
  )
}

function Tabla({ filas }) {
  return (
    <table className="tabla tabla-lista">
      <caption className="solo-lector">Invitaciones</caption>
      <thead>
        <tr>
          <th scope="col">Código</th>
          <th scope="col">Nombre</th>
          <th scope="col">Estado</th>
          <th scope="col">Lugares</th>
          <th scope="col">Invitado de</th>
          <th scope="col">Grupo</th>
          <th scope="col">Mesa</th>
          <th scope="col">Seguimiento</th>
        </tr>
      </thead>
      <tbody>
        {filas.map((fila) => (
          <tr key={fila.codigo} className={fila.archivada ? 'fila-archivada' : undefined}>
            <td className="codigo">{fila.codigo}</td>
            <td>
              <a href={enlaces.detalle(fila.codigo)}>{fila.nombre_mostrar}</a>
            </td>
            <td>
              <Estado estado={fila.estado_respuesta} />
            </td>
            <td className="numero">{lugares(fila)}</td>
            <td>{fila.lado || '—'}</td>
            <td>{fila.grupo || '—'}</td>
            <td className="numero">{fila.mesa ?? '—'}</td>
            <td>
              <Marcas fila={fila} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
