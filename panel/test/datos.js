// Datos ficticios para las pruebas del panel.
export function fila(extra = {}) {
  return {
    codigo: 'INV-001', nombre_mostrar: 'Familia Ficticia', adultos: 2, ninos_autorizados: 0, infantes: 0,
    pases: 2, estado_respuesta: 'pendiente', confirmados: null, lado: null, grupo: null, roles: [],
    no_planner: null, requiere_revision: false, enlace_activo: false, enlace_enviado: false, archivada: false,
    ...extra,
  }
}
