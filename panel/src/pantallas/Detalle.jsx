import { useCallback, useEffect, useState } from 'react'
import { usePanel } from '../App.jsx'
import { api } from '../api.js'
import { fechaHora, telefono } from '../formato.js'
import { enlaces } from '../rutas.js'
import { MOTIVO_REVISION, ORIGEN_RESPUESTA, textoError } from '../textos.js'
import { Cargando, Estado, MensajeError, MensajeOk, Titulo } from '../componentes/comunes.jsx'
import Dialogo from '../componentes/Dialogo.jsx'
import {
  SeccionDesbloqueo,
  SeccionEnlace,
  SeccionRecordatorios,
  SeccionRespuesta,
} from '../componentes/Secciones.jsx'

export default function Detalle({ codigo }) {
  const { esNovios } = usePanel()
  const [d, setD] = useState(null)
  const [historial, setHistorial] = useState([])
  const [error, setError] = useState(null)
  const [ok, setOk] = useState(null)
  const [dialogo, setDialogo] = useState(null) // 'archivar' | 'restaurar'
  const [ocupado, setOcupado] = useState(false)

  const cargar = useCallback(async () => {
    try {
      const [det, hist] = await Promise.all([api.detalle(codigo), api.historial(codigo)])
      setD(det)
      setHistorial(hist)
    } catch (e) {
      setError(e)
    }
  }, [codigo])

  useEffect(() => {
    cargar()
  }, [cargar])

  // Resultado de una acción de una sección: mensaje y recarga del detalle.
  const resultado = useCallback(
    (texto, e) => {
      setOk(e ? null : texto)
      setError(e || null)
      if (!e) cargar()
    },
    [cargar],
  )

  const archivarORestaurar = async () => {
    setOcupado(true)
    try {
      if (dialogo === 'archivar') await api.archivar(codigo)
      else await api.restaurar(codigo)
      const texto = dialogo === 'archivar' ? 'Invitación archivada. Su enlace quedó revocado.' : 'Invitación restaurada.'
      setDialogo(null)
      resultado(texto)
    } catch (e) {
      setDialogo(null)
      resultado(null, e)
    } finally {
      setOcupado(false)
    }
  }

  if (!d) {
    return (
      <section>
        <p>
          <a href={enlaces.lista}>← Invitaciones</a>
        </p>
        {error ? <MensajeError>{textoError(error)}</MensajeError> : <Cargando />}
      </section>
    )
  }

  return (
    <section className="detalle">
      <p className="migas">
        <a href={enlaces.lista}>← Invitaciones</a>
      </p>
      <Titulo sub={d.codigo}>{d.nombre_mostrar}</Titulo>
      <div className="detalle-estado">
        <Estado estado={d.estado_respuesta} />
        {d.archivada ? <span className="marca-archivada">Archivada el {fechaHora(d.archivada_en)}</span> : null}
        {d.requiere_revision ? <span className="marca-revision">⚑ En revisión</span> : null}
      </div>
      <div aria-live="polite">
        <MensajeOk>{ok}</MensajeOk>
      </div>
      <MensajeError>{error ? textoError(error) : null}</MensajeError>

      {esNovios ? (
        <div className="acciones acciones-pantalla">
          {!d.archivada ? (
            <a className="boton secundario" href={enlaces.editar(d.codigo)}>
              Editar
            </a>
          ) : null}
          <button type="button" className="boton secundario" onClick={() => setDialogo(d.archivada ? 'restaurar' : 'archivar')}>
            {d.archivada ? 'Restaurar' : 'Archivar'}
          </button>
        </div>
      ) : null}

      <div className="detalle-rejilla">
        <section className="panel" aria-labelledby="t-datos">
          <h2 id="t-datos">Datos</h2>
          <dl className="datos">
            <Dato t="Adultos" v={d.adultos} />
            <Dato t="Niños autorizados" v={d.ninos_autorizados} />
            <Dato t="Infantes" v={d.infantes} />
            <Dato t="Pases" v={d.pases} />
            {d.pases_planner_original != null && d.pases_planner_original !== d.pases ? (
              <Dato t="«# Pases» de la planner" v={d.pases_planner_original} />
            ) : null}
            <Dato t="Invitado de" v={d.lado} />
            <Dato t="Grupo" v={d.grupo} />
            <Dato t="Rol en la boda" v={d.roles.join(', ')} />
            <Dato t="Mesa" v={d.mesa} />
            <Dato t="No. de la planner" v={d.no_planner} />
            <Dato t="Teléfono principal" v={telefono(d.telefono_principal)} />
            <Dato t="Contacto alterno" v={d.contacto_alterno_nombre} />
            <Dato t="Teléfono del contacto alterno" v={telefono(d.contacto_alterno_tel)} />
            <Dato t="Nota interna" v={d.nota_interna} largo />
          </dl>
          {d.requiere_revision ? (
            <div className="revision">
              <h3>En revisión</h3>
              <ul>
                {d.motivos_revision.map((m) => (
                  <li key={m}>{MOTIVO_REVISION[m] || m}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>

        <SeccionRespuesta d={d} alTerminar={resultado} />
        {esNovios && !d.archivada ? <SeccionEnlace d={d} alTerminar={resultado} /> : null}
        {!d.archivada ? <SeccionRecordatorios d={d} alTerminar={resultado} /> : null}
        {esNovios && !d.archivada ? <SeccionDesbloqueo d={d} alTerminar={resultado} /> : null}

        <section className="panel" aria-labelledby="t-historial">
          <h2 id="t-historial">Historial de respuestas</h2>
          {historial.length === 0 ? (
            <p>Aún no hay respuestas.</p>
          ) : (
            <ol className="historial">
              {historial.map((v) => (
                <li key={v.numero} className={v.vigente ? 'vigente' : undefined}>
                  <p className="historial-cabeza">
                    <strong>
                      {v.asiste ? `Asiste: ${v.confirmados} lugar${v.confirmados === 1 ? '' : 'es'}` : 'No asiste'}
                    </strong>
                    {v.vigente ? <span className="etiqueta">Vigente</span> : null}
                  </p>
                  <p className="tenue">
                    {fechaHora(v.creada_en)} · por {ORIGEN_RESPUESTA[v.origen] || v.origen}
                    {v.actor ? ` (${v.actor})` : ''}
                  </p>
                  {v.alergias ? <p>Alergias: {v.alergias}</p> : null}
                  {v.mensaje ? <p className="mensaje-invitado">«{v.mensaje}»</p> : null}
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>

      <p className="tenue pie-detalle">
        Creada el {fechaHora(d.creada_en)} · actualizada el {fechaHora(d.actualizada_en)}
        {d.desbloqueada_hasta ? ` · desbloqueada hasta el ${fechaHora(d.desbloqueada_hasta)}` : ''}
      </p>

      {esNovios ? (
      <Dialogo
        abierto={dialogo !== null}
        titulo={dialogo === 'archivar' ? '¿Archivar esta invitación?' : '¿Restaurar esta invitación?'}
        confirmar={dialogo === 'archivar' ? 'Archivar' : 'Restaurar'}
        alConfirmar={archivarORestaurar}
        alCerrar={() => setDialogo(null)}
        ocupado={ocupado}
      >
        {dialogo === 'archivar' ? (
          <p>
            Sale de la lista, del resumen y de la exportación, y <strong>su enlace deja de funcionar</strong>. Puedes
            restaurarla después, pero tendrás que generar un enlace nuevo.
          </p>
        ) : (
          <p>Vuelve a la lista y al resumen. No recupera el enlace anterior.</p>
        )}
      </Dialogo>
      ) : null}
    </section>
  )
}

function Dato({ t, v, largo }) {
  const vacio = v === null || v === undefined || v === ''
  return (
    <div className={largo ? 'dato dato-largo' : 'dato'}>
      <dt>{t}</dt>
      <dd className={vacio ? 'tenue' : undefined}>{vacio ? '—' : v}</dd>
    </div>
  )
}

