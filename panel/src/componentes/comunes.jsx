import { useEffect, useRef } from 'react'
import { ESTADO } from '../textos.js'

// Error visible sin rojo (ADR 0029): «⚠», texto en bosque, borde oro-viejo. role="alert".
export function MensajeError({ children, id }) {
  if (!children) return null
  return (
    <div className="error" role="alert" id={id}>
      <span className="error-simbolo" aria-hidden="true">⚠</span>
      <span>{children}</span>
    </div>
  )
}

export function MensajeOk({ children }) {
  if (!children) return null
  return (
    <p className="ok" role="status">
      <span aria-hidden="true">✓ </span>
      {children}
    </p>
  )
}

export function Nota({ children }) {
  return <p className="nota">{children}</p>
}

export function Estado({ estado }) {
  const e = ESTADO[estado] || ESTADO.pendiente
  return (
    <span className={`estado estado-${estado}`}>
      <span aria-hidden="true">{e.simbolo} </span>
      {e.texto}
    </span>
  )
}

export function Cargando({ texto = 'Cargando…' }) {
  return (
    <p className="cargando" role="status">
      {texto}
    </p>
  )
}

// Título de pantalla que recibe el foco al navegar (lectores de pantalla y teclado).
export function Titulo({ children, sub }) {
  const ref = useRef(null)
  useEffect(() => {
    ref.current?.focus({ preventScroll: false })
  }, [])
  return (
    <header className="titulo-pantalla">
      <h1 ref={ref} tabIndex={-1}>
        {children}
      </h1>
      {sub ? <p className="sub">{sub}</p> : null}
    </header>
  )
}

// Campo con etiqueta, ayuda y error ligados por aria-describedby.
export function Campo({ id, etiqueta, ayuda, error, children, opcional }) {
  const ids = [ayuda ? `${id}-ayuda` : null, error ? `${id}-error` : null].filter(Boolean).join(' ')
  return (
    <div className={`campo${error ? ' campo-con-error' : ''}`}>
      <label htmlFor={id}>
        {etiqueta}
        {opcional ? <span className="opcional"> (opcional)</span> : null}
      </label>
      {children({ id, 'aria-describedby': ids || undefined, 'aria-invalid': error ? true : undefined })}
      {ayuda ? (
        <p className="ayuda" id={`${id}-ayuda`}>
          {ayuda}
        </p>
      ) : null}
      {error ? (
        <p className="error-campo" id={`${id}-error`}>
          <span aria-hidden="true">⚠ </span>
          {error}
        </p>
      ) : null}
    </div>
  )
}
