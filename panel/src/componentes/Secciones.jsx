// Secciones del detalle: respuesta, enlace (solo novios), recordatorios y desbloqueo.
import { useRef, useState } from 'react'
import { usePanel } from '../App.jsx'
import { api } from '../api.js'
import { fases } from '../fases.js'
import { diaLocal, fechaDia, fechaHora, finDelDia } from '../formato.js'
import { CAMPO, MOTIVO_CAMPO, ORIGEN_ENVIO, ORIGEN_RESPUESTA, TIPO_RECORDATORIO, textoError } from '../textos.js'
import { Campo, Estado, MensajeError, Nota } from './comunes.jsx'
import Dialogo from './Dialogo.jsx'
import VistaWhatsapp from './VistaWhatsapp.jsx'

const diaAntes = (iso) => diaLocal(new Date(Date.parse(iso) - 1))

// --------------------------------------------------------------------------- respuesta
export function SeccionRespuesta({ d, alTerminar }) {
  const { esNovios } = usePanel()
  const [editando, setEditando] = useState(false)
  return (
    <section className="panel" aria-labelledby="t-respuesta">
      <h2 id="t-respuesta">Respuesta</h2>
      <dl className="datos">
        <div className="dato">
          <dt>Estado</dt>
          <dd>
            <Estado estado={d.estado_respuesta} />
          </dd>
        </div>
        <div className="dato">
          <dt>Lugares confirmados</dt>
          <dd>{d.estado_respuesta === 'pendiente' ? '—' : `${d.confirmados} de ${d.pases}`}</dd>
        </div>
        {d.ultima_respuesta_en ? (
          <div className="dato">
            <dt>Última respuesta</dt>
            <dd>
              {fechaHora(d.ultima_respuesta_en)} · por {ORIGEN_RESPUESTA[d.ultima_respuesta_origen]}
            </dd>
          </div>
        ) : null}
        <div className="dato dato-largo">
          <dt>Alergias</dt>
          <dd className={d.alergias ? undefined : 'tenue'}>{d.alergias || '—'}</dd>
        </div>
        <div className="dato dato-largo">
          <dt>Mensaje del invitado</dt>
          <dd className={d.mensaje ? 'mensaje-invitado' : 'tenue'}>{d.mensaje || '—'}</dd>
        </div>
      </dl>
      {esNovios && !d.archivada ? (
        editando ? (
          <FormularioRespuesta
            d={d}
            alCancelar={() => setEditando(false)}
            alGuardar={() => {
              setEditando(false)
              alTerminar('Respuesta registrada.')
            }}
          />
        ) : (
          <button type="button" className="boton secundario" onClick={() => setEditando(true)}>
            Registrar respuesta
          </button>
        )
      ) : null}
    </section>
  )
}

function FormularioRespuesta({ d, alCancelar, alGuardar }) {
  const [asiste, setAsiste] = useState(d.estado_respuesta !== 'no_asiste')
  const [confirmados, setConfirmados] = useState(String(d.confirmados || d.pases))
  const [alergias, setAlergias] = useState(d.alergias || '')
  const [mensaje, setMensaje] = useState(d.mensaje || '')
  const [error, setError] = useState(null)
  const [ocupado, setOcupado] = useState(false)

  const guardar = async (e) => {
    e.preventDefault()
    setOcupado(true)
    setError(null)
    try {
      await api.responder(d.codigo, {
        asiste,
        confirmados: asiste ? Number.parseInt(confirmados, 10) || 0 : 0,
        alergias: alergias.trim() || null,
        mensaje: mensaje.trim() || null,
      })
      alGuardar()
    } catch (err) {
      setError(err)
    } finally {
      setOcupado(false)
    }
  }
  const errCampo = (c) => (error?.fields?.[c] ? MOTIVO_CAMPO[error.fields[c]] || MOTIVO_CAMPO.fuera_de_rango : null)

  return (
    <form className="formulario-respuesta" onSubmit={guardar} noValidate>
      <p className="nota">Registra aquí lo que el invitado te dijo por otro medio. Queda en el historial.</p>
      <fieldset className="opciones">
        <legend>¿Asiste?</legend>
        <label>
          <input type="radio" name="asiste" checked={asiste} onChange={() => setAsiste(true)} /> Sí
        </label>
        <label>
          <input type="radio" name="asiste" checked={!asiste} onChange={() => setAsiste(false)} /> No
        </label>
      </fieldset>
      {asiste ? (
        <Campo id="r-confirmados" etiqueta={`Lugares confirmados (1 a ${d.pases})`}
          error={error?.code === 'confirmados_fuera_de_rango' ? textoError(error) : errCampo('confirmados')}>
          {(p) => (
            <input {...p} type="number" inputMode="numeric" min="1" max={d.pases} value={confirmados}
              onChange={(e) => setConfirmados(e.target.value)} />
          )}
        </Campo>
      ) : null}
      <Campo id="r-alergias" etiqueta="Alergias" opcional error={errCampo('alergias')}>
        {(p) => <textarea {...p} rows="2" value={alergias} onChange={(e) => setAlergias(e.target.value)} />}
      </Campo>
      <Campo id="r-mensaje" etiqueta="Mensaje" opcional error={errCampo('mensaje')}>
        {(p) => <textarea {...p} rows="3" value={mensaje} onChange={(e) => setMensaje(e.target.value)} />}
      </Campo>
      {error && error.code !== 'confirmados_fuera_de_rango' && error.code !== 'validacion' ? (
        <MensajeError>{textoError(error)}</MensajeError>
      ) : null}
      <div className="acciones">
        <button type="submit" className="boton" disabled={ocupado}>
          Guardar respuesta
        </button>
        <button type="button" className="boton secundario" onClick={alCancelar} disabled={ocupado}>
          Cancelar
        </button>
      </div>
    </form>
  )
}

// --------------------------------------------------------------------------- enlace (solo novios)
export function SeccionEnlace({ d, alTerminar }) {
  const [url, setUrl] = useState(null)
  const [wa, setWa] = useState(null) // { destino, mensaje }
  const [dialogo, setDialogo] = useState(null) // 'regenerar' | 'revocar'
  const [ocupado, setOcupado] = useState(false)
  const [nota, setNota] = useState(null)
  const campoUrl = useRef(null)

  const accion = async (fn, texto) => {
    setOcupado(true)
    setNota(null)
    try {
      const r = await fn()
      alTerminar(texto)
      return r
    } catch (e) {
      alTerminar(null, e)
      return null
    } finally {
      setOcupado(false)
    }
  }

  const ver = async () => {
    if (url) return setUrl(null)
    setOcupado(true)
    try {
      setUrl((await api.verEnlace(d.codigo)).url)
    } catch (e) {
      alTerminar(null, e)
    } finally {
      setOcupado(false)
    }
  }

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(url)
      setNota('Enlace copiado.')
    } catch {
      campoUrl.current?.select()
      setNota('Tu navegador no permitió copiar: el enlace quedó seleccionado; cópialo manualmente.')
    }
  }

  const prepararWhatsapp = async (destino) => {
    setOcupado(true)
    try {
      setWa({ destino, mensaje: await api.whatsappEnlace(d.codigo, destino) })
    } catch (e) {
      alTerminar(null, e)
    } finally {
      setOcupado(false)
    }
  }

  const confirmarDialogo = async () => {
    const regenerar = dialogo === 'regenerar'
    const r = await accion(
      () => (regenerar ? api.regenerarEnlace(d.codigo) : api.revocarEnlace(d.codigo)),
      regenerar ? 'Enlace regenerado. El anterior ya no funciona.' : 'Enlace revocado.',
    )
    setDialogo(null)
    setWa(null)
    setUrl(regenerar && r ? r.url : null)
  }

  return (
    <section className="panel" aria-labelledby="t-enlace">
      <h2 id="t-enlace">Enlace personal</h2>
      <dl className="datos">
        <div className="dato">
          <dt>Estado</dt>
          <dd>{d.enlace_activo ? 'Activo' : 'Sin enlace'}</dd>
        </div>
        <div className="dato">
          <dt>Envío</dt>
          <dd>
            {d.enlace_enviado
              ? `Enviado el ${fechaHora(d.enlace_enviado_en)} por ${ORIGEN_ENVIO[d.enlace_enviado_origen] || d.enlace_enviado_origen}`
              : 'Sin enviar'}
          </dd>
        </div>
      </dl>

      {!d.enlace_activo ? (
        <>
          {d.requiere_revision ? <Nota>Corrige los datos en revisión antes de generar el enlace.</Nota> : null}
          <button
            type="button"
            className="boton"
            disabled={ocupado || d.requiere_revision}
            onClick={async () => {
              const r = await accion(() => api.generarEnlace(d.codigo), 'Enlace generado.')
              if (r) setUrl(r.url)
            }}
          >
            Generar enlace
          </button>
        </>
      ) : (
        <>
          <div className="acciones">
            <button type="button" className="boton secundario" onClick={ver} disabled={ocupado} aria-expanded={url !== null}>
              {url ? 'Ocultar enlace' : 'Ver enlace'}
            </button>
            {d.telefono_principal ? (
              <button type="button" className="boton" onClick={() => prepararWhatsapp('principal')} disabled={ocupado}>
                WhatsApp al principal
              </button>
            ) : null}
            {d.contacto_alterno_tel ? (
              <button type="button" className="boton" onClick={() => prepararWhatsapp('alterno')} disabled={ocupado}>
                WhatsApp al alterno
              </button>
            ) : null}
          </div>
          {!d.telefono_principal && !d.contacto_alterno_tel ? (
            <Nota>Sin teléfonos: copia el enlace y envíalo por otro medio.</Nota>
          ) : null}
          {url ? (
            <div className="campo-enlace">
              <label htmlFor="url-enlace">Enlace de la invitación</label>
              <div className="fila-copiar">
                <input id="url-enlace" ref={campoUrl} type="text" readOnly value={url} onFocus={(e) => e.target.select()} />
                <button type="button" className="boton secundario" onClick={copiar}>
                  Copiar
                </button>
              </div>
              <button
                type="button"
                className="boton enlace-boton"
                disabled={ocupado}
                onClick={() => accion(() => api.enlaceEnviado(d.codigo, 'manual'), 'Enlace marcado como enviado por otro medio.')}
              >
                Marcar como enviado por otro medio
              </button>
            </div>
          ) : null}
          {nota ? (
            <p className="ok" role="status">
              {nota}
            </p>
          ) : null}
          {wa ? (
            <VistaWhatsapp
              mensaje={wa.mensaje}
              etiquetaMarcar="Marcar enlace como enviado"
              ocupado={ocupado}
              alCerrar={() => setWa(null)}
              alMarcar={async () => {
                await accion(() => api.enlaceEnviado(d.codigo, 'whatsapp'), 'Enlace marcado como enviado por WhatsApp.')
                setWa(null)
              }}
            />
          ) : null}
          <div className="acciones acciones-peligro">
            <button type="button" className="boton secundario" onClick={() => setDialogo('regenerar')} disabled={ocupado}>
              Regenerar enlace
            </button>
            <button type="button" className="boton secundario" onClick={() => setDialogo('revocar')} disabled={ocupado}>
              Revocar enlace
            </button>
          </div>
        </>
      )}
      <Dialogo
        abierto={dialogo !== null}
        titulo={dialogo === 'regenerar' ? '¿Regenerar el enlace?' : '¿Revocar el enlace?'}
        confirmar={dialogo === 'regenerar' ? 'Regenerar' : 'Revocar'}
        alConfirmar={confirmarDialogo}
        alCerrar={() => setDialogo(null)}
        ocupado={ocupado}
      >
        <p>
          El enlace actual <strong>dejará de funcionar</strong>.{' '}
          {dialogo === 'regenerar'
            ? 'Se crea uno nuevo que tendrás que volver a enviar.'
            : 'La invitación se queda sin enlace hasta que generes otro.'}
        </p>
      </Dialogo>
    </section>
  )
}

// --------------------------------------------------------------------------- recordatorios
export function SeccionRecordatorios({ d, alTerminar }) {
  const { config, reloj } = usePanel()
  const f = fases(config, reloj())
  const [wa, setWa] = useState(null)
  const [ocupado, setOcupado] = useState(false)

  const preparar = async (destino) => {
    setOcupado(true)
    try {
      setWa({ destino, mensaje: await api.recordatorio(d.codigo, destino) })
    } catch (e) {
      alTerminar(null, e)
    } finally {
      setOcupado(false)
    }
  }
  const marcar = async () => {
    setOcupado(true)
    try {
      await api.recordatorioEnviado(d.codigo, wa.destino)
      setWa(null)
      alTerminar('Recordatorio marcado como enviado.')
    } catch (e) {
      alTerminar(null, e)
    } finally {
      setOcupado(false)
    }
  }

  return (
    <section className="panel" aria-labelledby="t-recordatorios">
      <h2 id="t-recordatorios">Recordatorios</h2>
      <p>
        {f.recordatoriosCerrados
          ? 'El periodo de recordatorios terminó.'
          : f.tipoRecordatorio === 'confirmar'
            ? `Toca el recordatorio para confirmar (hasta el ${fechaDia(config.fecha_limite_mostrar)}). No lleva el enlace.`
            : `Toca el recordatorio del evento (hasta el ${fechaDia(diaAntes(config.cierre_planner))}). No lleva el enlace.`}
      </p>
      <p className="tenue">
        {d.recordatorios
          ? `${d.recordatorios} enviado${d.recordatorios > 1 ? 's' : ''}; el último ${TIPO_RECORDATORIO[d.ultimo_recordatorio_tipo]}, el ${fechaHora(d.ultimo_recordatorio_en)}`
          : 'Aún no se ha enviado ningún recordatorio.'}
      </p>
      {!f.recordatoriosCerrados ? (
        <div className="acciones">
          {d.telefono_principal ? (
            <button type="button" className="boton" onClick={() => preparar('principal')} disabled={ocupado}>
              Recordatorio al principal
            </button>
          ) : null}
          {d.contacto_alterno_tel ? (
            <button type="button" className="boton" onClick={() => preparar('alterno')} disabled={ocupado}>
              Recordatorio al alterno
            </button>
          ) : null}
          {!d.telefono_principal && !d.contacto_alterno_tel ? <Nota>La invitación no tiene teléfonos.</Nota> : null}
        </div>
      ) : null}
      {wa ? (
        <VistaWhatsapp
          mensaje={wa.mensaje}
          etiquetaMarcar="Marcar recordatorio como enviado"
          ocupado={ocupado}
          alCerrar={() => setWa(null)}
          alMarcar={marcar}
        />
      ) : null}
    </section>
  )
}

// --------------------------------------------------------------------------- desbloqueo (solo novios)
export function SeccionDesbloqueo({ d, alTerminar }) {
  const { config, reloj } = usePanel()
  const ahora = reloj()
  const f = fases(config, ahora)
  const ultimo = diaAntes(config.congelamiento)
  const minimo = diaLocal(ahora)
  const [dia, setDia] = useState(minimo <= ultimo ? minimo : ultimo)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState(null)
  const vigente = d.desbloqueada_hasta && Date.parse(d.desbloqueada_hasta) > ahora.getTime()

  const desbloquear = async (e) => {
    e.preventDefault()
    setOcupado(true)
    setError(null)
    try {
      await api.desbloquear(d.codigo, finDelDia(dia))
      alTerminar(`Invitación desbloqueada hasta el final del ${fechaDia(dia)}.`)
    } catch (err) {
      if (err.code === 'validacion') setError(MOTIVO_CAMPO[err.fields?.hasta] || textoError(err))
      else alTerminar(null, err)
    } finally {
      setOcupado(false)
    }
  }
  const retirar = async () => {
    setOcupado(true)
    try {
      await api.retirarDesbloqueo(d.codigo)
      alTerminar('Desbloqueo retirado.')
    } catch (e) {
      alTerminar(null, e)
    } finally {
      setOcupado(false)
    }
  }

  return (
    <section className="panel" aria-labelledby="t-desbloqueo">
      <h2 id="t-desbloqueo">Desbloqueo</h2>
      {vigente ? (
        <>
          <p>Desbloqueada hasta el {fechaHora(d.desbloqueada_hasta)}: el invitado puede confirmar o cambiar su respuesta.</p>
          <button type="button" className="boton secundario" onClick={retirar} disabled={ocupado}>
            Retirar desbloqueo
          </button>
        </>
      ) : null}
      {f.plazoAbierto ? (
        <Nota>
          El plazo sigue abierto hasta el {fechaDia(config.fecha_limite_mostrar)}: el invitado aún puede responder.
          Después podrás desbloquear hasta el {fechaDia(ultimo)}.
        </Nota>
      ) : f.congelada ? (
        <Nota>Desde el {fechaDia(diaLocal(new Date(config.congelamiento)))} la confirmación de los invitados está congelada; ya no se puede desbloquear.</Nota>
      ) : (
        <form className="formulario-desbloqueo" onSubmit={desbloquear} noValidate>
          <Campo id="desbloqueo-dia" etiqueta={CAMPO.hasta} ayuda={`Incluye el día completo. Último día posible: ${fechaDia(ultimo)}.`} error={error}>
            {(p) => <input {...p} type="date" min={minimo} max={ultimo} value={dia} onChange={(e) => setDia(e.target.value)} required />}
          </Campo>
          <button type="submit" className="boton" disabled={ocupado || !dia}>
            {vigente ? 'Cambiar desbloqueo' : 'Desbloquear'}
          </button>
        </form>
      )}
    </section>
  )
}
