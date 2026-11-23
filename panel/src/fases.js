// Fases del calendario (ADR 0025, 0026, 0027) con la hora del SERVIDOR (`ahora` de /config).
// Solo sirven para mostrar u ocultar botones; quien decide es la API.

export function relojDelServidor(config, ahoraLocal = Date.now()) {
  const desfase = Date.parse(config.ahora) - ahoraLocal
  return () => new Date(Date.now() + desfase)
}

export function fases(config, ahora) {
  const t = ahora.getTime()
  const cierre = Date.parse(config.cierre_plazo)
  const congela = Date.parse(config.congelamiento)
  const planner = Date.parse(config.cierre_planner)
  return {
    plazoAbierto: t < cierre,
    puedeDesbloquear: t >= cierre && t < congela,
    congelada: t >= congela,
    tipoRecordatorio: t < cierre ? 'confirmar' : t < planner ? 'evento' : null,
    recordatoriosCerrados: t >= planner,
  }
}
