// Cierre por inactividad en el navegador (ADR 0029): 30 min sin interacción → logout.
// Se basa en la hora de la última interacción (no solo en un temporizador), porque el
// celular suspende los temporizadores con la pantalla apagada.

export const INACTIVIDAD_MS = 30 * 60 * 1000
const EVENTOS = ['pointerdown', 'keydown', 'touchstart', 'wheel', 'input']

export function vigilarInactividad(alVencer, ms = INACTIVIDAD_MS, ahora = () => Date.now()) {
  let ultima = ahora()
  let vencida = false
  const tocar = () => {
    if (!vencida) ultima = ahora()
  }
  const revisar = () => {
    if (!vencida && ahora() - ultima >= ms) {
      vencida = true
      alVencer()
    }
  }
  EVENTOS.forEach((e) => window.addEventListener(e, tocar, { passive: true, capture: true }))
  document.addEventListener('visibilitychange', revisar)
  const intervalo = window.setInterval(revisar, Math.min(30_000, ms))
  return () => {
    EVENTOS.forEach((e) => window.removeEventListener(e, tocar, { capture: true }))
    document.removeEventListener('visibilitychange', revisar)
    window.clearInterval(intervalo)
  }
}
