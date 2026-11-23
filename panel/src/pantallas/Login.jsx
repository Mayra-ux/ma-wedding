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
        <img src={`${import.meta.env.BASE_URL}mono.webp`} alt="Monograma M&A" width="96" height="96" />
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
        <p className="nota">Solo para los novios y la planner.</p>
      </div>
    </main>
  )
}
