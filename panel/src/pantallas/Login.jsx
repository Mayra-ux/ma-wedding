import { useEffect, useRef } from 'react'

const MOTIVOS = {
  sesion_terminada: 'Tu sesión terminó. Vuelve a entrar.',
  inactividad: 'Cerramos tu sesión tras 30 minutos sin actividad. Vuelve a entrar.',
  cerrada: 'Cerraste sesión.',
}

export default function Login({ motivo }) {
  const ref = useRef(null)
  useEffect(() => {
    ref.current?.focus()
  }, [])
  return (
    <main className="login">
      <div className="login-tarjeta">
        {/* Monograma tal cual (proporción original 1400×655) con el mismo brillo de la invitación */}
        <div className="login-mono">
          <img src={`${import.meta.env.BASE_URL}mono.webp`} alt="Monograma M&A" width="1400" height="655" />
          <span className="login-brillo" aria-hidden="true" />
        </div>
        <h1 ref={ref} tabIndex={-1}>
          Panel de la boda
        </h1>
        <p className="login-sub">Mayra &amp; Alejandro</p>
        {motivo ? (
          <p className="login-motivo" role="status">
            {MOTIVOS[motivo]}
          </p>
        ) : null}
        <a className="boton boton-grande" href="/api/v1/auth/google/login">
          Entrar con Google
        </a>
        <p className="nota">Acceso de administrador</p>
      </div>
    </main>
  )
}
