import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { alPerderSesion, api, fijarCsrf } from './api.js'
import { relojDelServidor } from './fases.js'
import { vigilarInactividad } from './inactividad.js'
import { enlaces, useRuta } from './rutas.js'
import { ROL_USUARIO, textoError } from './textos.js'
import { Cargando, MensajeError } from './componentes/comunes.jsx'
import Login from './pantallas/Login.jsx'
import Lista from './pantallas/Lista.jsx'
import Detalle from './pantallas/Detalle.jsx'
import Formulario from './pantallas/Formulario.jsx'
import Importar from './pantallas/Importar.jsx'
import Exportar from './pantallas/Exportar.jsx'
import Actividad from './pantallas/Actividad.jsx'

const Contexto = createContext(null)
export const usePanel = () => useContext(Contexto)

export function Proveedor({ valor, children }) {
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export default function App() {
  const [estado, setEstado] = useState({ fase: 'cargando' })

  const salir = useCallback((motivo) => {
    fijarCsrf(null)
    setEstado({ fase: 'anonimo', motivo })
  }, [])

  useEffect(() => {
    let vivo = true
    ;(async () => {
      try {
        const me = await api.me()
        fijarCsrf(me.csrf_token)
        const config = await api.config()
        if (vivo) setEstado({ fase: 'sesion', me, config, reloj: relojDelServidor(config) })
      } catch (e) {
        if (!vivo) return
        if (e.status === 401) setEstado({ fase: 'anonimo' })
        else setEstado({ fase: 'error', error: e })
      }
    })()
    return () => {
      vivo = false
    }
  }, [])

  useEffect(() => alPerderSesion(() => salir('sesion_terminada')), [salir])

  const enSesion = estado.fase === 'sesion'
  useEffect(() => {
    if (!enSesion) return undefined
    return vigilarInactividad(async () => {
      try {
        await api.logout()
      } catch {
        /* la sesión ya no existe en el servidor */
      }
      salir('inactividad')
    })
  }, [enSesion, salir])

  if (estado.fase === 'cargando') return <Cargando texto="Abriendo el panel…" />
  if (estado.fase === 'anonimo') return <Login motivo={estado.motivo} />
  if (estado.fase === 'error')
    return (
      <main className="contenido">
        <MensajeError>{textoError(estado.error)}</MensajeError>
      </main>
    )
  return <PanelConSesion estado={estado} salir={salir} />
}

function PanelConSesion({ estado, salir }) {
  const { me, config, reloj } = estado
  const ruta = useRuta()
  const esNovios = me.rol === 'admin'
  const valor = useMemo(() => ({ me, config, reloj, esNovios }), [me, config, reloj, esNovios])

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [ruta])

  const cerrarSesion = async () => {
    try {
      await api.logout()
    } catch {
      /* sin sesión */
    }
    salir('cerrada')
  }

  return (
    <Proveedor valor={valor}>
      <a className="saltar" href="#contenido" onClick={saltar}>
        Saltar al contenido
      </a>
      <header className="barra">
        <div className="barra-fila">
          <a className="marca" href={enlaces.lista}>
            <img src={`${import.meta.env.BASE_URL}mono.webp`} alt="" width="40" height="40" />
            <span>Panel M&amp;A</span>
          </a>
          <div className="usuario">
            <span className="rol-usuario">{ROL_USUARIO[me.rol]}</span>
            <span className="correo" title={me.correo}>
              {me.correo}
            </span>
          </div>
          <button type="button" className="boton salir" onClick={cerrarSesion}>
            Cerrar sesión
          </button>
        </div>
        <nav aria-label="Secciones">
          <ul className="menu">
            <Item href={enlaces.lista} activo={['lista', 'detalle', 'editar', 'nueva'].includes(ruta.nombre)}>
              Invitaciones
            </Item>
            {esNovios ? (
              <Item href={enlaces.importar} activo={ruta.nombre === 'importar'}>
                Importar
              </Item>
            ) : null}
            <Item href={enlaces.exportar} activo={ruta.nombre === 'exportar'}>
              Exportar
            </Item>
            <Item href={enlaces.actividad} activo={ruta.nombre === 'actividad'}>
              Actividad
            </Item>
          </ul>
        </nav>
      </header>
      <main id="contenido" className="contenido" tabIndex={-1}>
        <Pantalla ruta={ruta} esNovios={esNovios} />
      </main>
    </Proveedor>
  )
}

function saltar(e) {
  e.preventDefault() // el hash es del enrutador: se mueve el foco sin cambiar la ruta
  document.getElementById('contenido')?.focus()
}

function Item({ href, activo, children }) {
  return (
    <li>
      <a href={href} aria-current={activo ? 'page' : undefined}>
        {children}
      </a>
    </li>
  )
}

function Pantalla({ ruta, esNovios }) {
  switch (ruta.nombre) {
    case 'lista':
      return <Lista />
    case 'detalle':
      return <Detalle key={ruta.codigo} codigo={ruta.codigo} />
    case 'editar':
      return esNovios ? <Formulario key={ruta.codigo} codigo={ruta.codigo} /> : <SinPermiso />
    case 'nueva':
      return esNovios ? <Formulario key="nueva" /> : <SinPermiso />
    case 'importar':
      return esNovios ? <Importar /> : <SinPermiso />
    case 'exportar':
      return <Exportar />
    case 'actividad':
      return <Actividad />
    default:
      return <NoEncontrada />
  }
}

function SinPermiso() {
  return (
    <section>
      <h1>Sin permiso</h1>
      <p>Esta sección es solo para los novios.</p>
      <p>
        <a href={enlaces.lista}>Volver a las invitaciones</a>
      </p>
    </section>
  )
}

function NoEncontrada() {
  return (
    <section>
      <h1>Página no encontrada</h1>
      <p>
        <a href={enlaces.lista}>Volver a las invitaciones</a>
      </p>
    </section>
  )
}
