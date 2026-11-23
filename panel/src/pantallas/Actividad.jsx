// Auditoría (ADR 0026): la ven novios y planner. Los detalles nunca llevan datos personales.
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { normalizar } from '../filtros.js'
import { fechaHora } from '../formato.js'
import { enlaces } from '../rutas.js'
import { ACCION_AUDITORIA, textoError } from '../textos.js'
import { Cargando, MensajeError, Titulo } from '../componentes/comunes.jsx'

const PAGINA = 100

function textoDetalle(detalle) {
  return Object.entries(detalle || {})
    .map(([k, v]) => `${k.replaceAll('_', ' ')}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
    .join(' · ')
}

export default function Actividad() {
  const [eventos, setEventos] = useState(null)
  const [error, setError] = useState(null)
  const [q, setQ] = useState('')
  const [limite, setLimite] = useState(PAGINA)

  useEffect(() => {
    api.auditoria().then(setEventos, setError)
  }, [])

  const visibles = useMemo(() => {
    if (!eventos) return []
    const n = normalizar(q)
    if (!n) return eventos
    return eventos.filter((e) =>
      normalizar(`${e.actor} ${ACCION_AUDITORIA[e.accion] || e.accion} ${e.codigo_invitacion || ''}`).includes(n),
    )
  }, [eventos, q])

  return (
    <section>
      <Titulo>Actividad</Titulo>
      <p className="nota">Quién hizo qué y cuándo, del más reciente al más antiguo.</p>
      <MensajeError>{error ? textoError(error) : null}</MensajeError>
      {!eventos && !error ? <Cargando /> : null}
      {eventos ? (
        <>
          <div className="busqueda">
            <label htmlFor="buscar-actividad">Buscar por persona, acción o código</label>
            <input id="buscar-actividad" type="search" value={q} onChange={(e) => { setQ(e.target.value); setLimite(PAGINA) }} autoComplete="off" />
          </div>
          <p className="conteo" role="status" aria-live="polite">{visibles.length} eventos</p>
          <ol className="actividad">
            {visibles.slice(0, limite).map((e, i) => (
              <li key={`${e.creado_en}-${i}`}>
                <p>
                  <strong>{ACCION_AUDITORIA[e.accion] || e.accion}</strong>
                  {e.codigo_invitacion ? (
                    <>
                      {' '}
                      <a href={enlaces.detalle(e.codigo_invitacion)}>{e.codigo_invitacion}</a>
                    </>
                  ) : null}
                </p>
                <p className="tenue">
                  {fechaHora(e.creado_en)} · {e.actor}
                </p>
                {Object.keys(e.detalle || {}).length ? <p className="tenue detalle-evento">{textoDetalle(e.detalle)}</p> : null}
              </li>
            ))}
          </ol>
          {visibles.length > limite ? (
            <button type="button" className="boton secundario" onClick={() => setLimite((l) => l + PAGINA)}>
              Mostrar más
            </button>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
