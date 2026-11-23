// Formatos de fecha y teléfono. Siempre en hora del centro de México.
const ZONA = 'America/Mexico_City'

const FECHA_HORA = new Intl.DateTimeFormat('es-MX', {
  timeZone: ZONA,
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})
const FECHA_LARGA = new Intl.DateTimeFormat('es-MX', {
  timeZone: ZONA,
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

export function fechaHora(iso) {
  return iso ? FECHA_HORA.format(new Date(iso)) : ''
}

export function fechaLarga(iso) {
  return iso ? FECHA_LARGA.format(new Date(iso)) : ''
}

// "2027-01-30" → "sábado, 30 de enero de 2027" (fecha local, sin zona).
export function fechaDia(aaaammdd) {
  if (!aaaammdd) return ''
  const [a, m, d] = aaaammdd.split('-').map(Number)
  return fechaLarga(new Date(Date.UTC(a, m - 1, d, 18)).toISOString())
}

// Día local (AAAA-MM-DD) de un instante, en hora del centro de México.
export function diaLocal(fecha) {
  const p = new Intl.DateTimeFormat('en-CA', { timeZone: ZONA, year: 'numeric', month: '2-digit', day: '2-digit' })
  return p.format(fecha)
}

// Fin del día local elegido = 00:00 (−06:00) del día siguiente.
export function finDelDia(aaaammdd) {
  const [a, m, d] = aaaammdd.split('-').map(Number)
  return new Date(Date.UTC(a, m - 1, d + 1, 6)).toISOString()
}

export function telefono(e164) {
  if (!e164) return ''
  const m = /^\+52(\d{3})(\d{3})(\d{4})$/.exec(e164)
  return m ? `+52 ${m[1]} ${m[2]} ${m[3]}` : e164
}
