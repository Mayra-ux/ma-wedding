// Textos de la interfaz del panel, en un solo lugar (español de México).
// Los mensajes de WhatsApp NO están aquí: los arma la API (ADR 0026 y 0029).

export const ESTADO = {
  confirmada: { simbolo: '✓', texto: 'Confirmada' },
  pendiente: { simbolo: '○', texto: 'Pendiente' },
  no_asiste: { simbolo: '✕', texto: 'No asiste' },
}

export const ROL_USUARIO = { admin: 'Novios', lector: 'Planner' }

export const MOTIVO_REVISION = {
  pases_inconsistentes: '«# Pases» de la planner no coincide con adultos + niños',
  lado_invalido: 'Lado no válido',
  grupo_invalido: 'Grupo no válido',
  telefono_invalido: 'Teléfono no válido',
  rol_invalido: 'Rol no válido',
}

export const ORIGEN_RESPUESTA = { invitado: 'el invitado', admin: 'los novios' }
export const ORIGEN_ENVIO = { whatsapp: 'WhatsApp', manual: 'otro medio' }
export const TIPO_RECORDATORIO = { confirmar: 'para confirmar', evento: 'del evento' }

// Errores de la API por código. Si llega uno desconocido se usa `error_interno`.
export const ERRORES = {
  sin_conexion: 'No hay conexión con el servidor. Revisa tu internet e inténtalo de nuevo.',
  solicitud_invalida: 'La solicitud no es válida. Recarga el panel e inténtalo de nuevo.',
  validacion: 'Revisa los campos marcados.',
  cuerpo_demasiado_grande: 'El archivo es demasiado grande (máximo 2 MB).',
  demasiadas_solicitudes: 'Demasiados intentos seguidos. Espera unos minutos.',
  no_encontrado: 'No se encontró esa invitación.',
  error_interno: 'Ocurrió un error. Inténtalo de nuevo.',
  no_autenticado: 'Tu sesión terminó. Vuelve a entrar.',
  sin_permiso: 'Tu cuenta no tiene permiso para esta acción.',
  csrf_invalido: 'La solicitud no es válida. Recarga el panel e inténtalo de nuevo.',
  auth_no_configurada: 'El inicio de sesión no está configurado en este servidor.',
  pases_menores_que_confirmados:
    'No puedes asignar menos lugares de los ya confirmados. Primero registra la respuesta corregida.',
  confirmados_fuera_de_rango: 'Los lugares confirmados deben ir de 1 a los pases asignados si asiste, o 0 si no asiste.',
  ya_archivada: 'La invitación ya está archivada.',
  no_archivada: 'La invitación no está archivada.',
  archivada: 'La invitación está archivada. Restáurala primero.',
  plazo_aun_abierto: 'El plazo de confirmación sigue abierto; todavía no se puede desbloquear.',
  mas_alla_del_congelamiento: 'El desbloqueo no puede pasar del 5 de febrero de 2027.',
  rsvp_congelado: 'La confirmación de los invitados ya está congelada; ya no se puede desbloquear.',
  sin_enlace_activo: 'La invitación no tiene enlace activo.',
  requiere_revision: 'Corrige los datos marcados en revisión antes de generar el enlace.',
  ya_tiene_enlace: 'La invitación ya tiene un enlace activo.',
  recordatorios_cerrados: 'El periodo de recordatorios terminó.',
  sin_telefono: 'La invitación no tiene ese teléfono.',
  conflicto_codigo: 'No se pudo asignar el código. Inténtalo de nuevo.',
  formato_no_soportado: 'Solo se aceptan archivos .xlsx o .csv (no .xls ni archivos con macros).',
  archivo_no_valido: 'El archivo no es válido o está dañado.',
  columnas_faltantes: 'Al archivo le faltan columnas de la planner.',
  hoja_requerida: 'El archivo tiene varias hojas de invitados. Elige cuál importar.',
  hoja_no_encontrada: 'No se encontró esa hoja de invitados en el archivo.',
  archivo_con_errores: 'El archivo tiene filas con errores; no se aplicó nada.',
}

export function textoError(error) {
  return ERRORES[error?.code] || ERRORES.error_interno
}

// Motivos de error por campo (422 validacion).
export const MOTIVO_CAMPO = {
  obligatorio: 'Este campo es obligatorio.',
  fuera_de_rango: 'El número no está en el rango permitido.',
  fuera_de_catalogo: 'Elige una opción de la lista.',
  demasiado_largo: 'El texto es demasiado largo.',
  caracteres_no_permitidos: 'El texto tiene caracteres no permitidos.',
  telefono_invalido: 'Escribe 10 dígitos, o el número con lada internacional (+…).',
  repetido: 'Hay valores repetidos.',
  en_el_pasado: 'La fecha ya pasó.',
  demasiadas: 'El archivo tiene demasiadas filas.',
}

export const ERROR_FILA = {
  codigo_invalido: 'Código INV no válido',
  codigo_desconocido: 'Ese Código INV no existe en el sistema',
  archivada: 'Esa invitación está archivada',
  nombre_faltante: 'Falta «Nombre Invitado»',
  nombre_invalido: '«Nombre Invitado» no válido',
  adultos_faltante: 'Falta «Adultos»',
  adultos_invalido: '«Adultos» no válido',
  ninos_invalido: '«# de Niños» no válido',
  infantes_invalido: '«Infante» no válido',
  pases_invalido: '«# Pases» no válido',
  mesa_invalida: '«# de mesa» no válido',
  no_invalido: '«No.» no válido',
  contacto_invalido: '«Nombre Contacto Alterno» no válido',
  comentario_invalido: '«Comentario» no válido',
  pases_menores_que_confirmados: 'Los pases quedarían por debajo de los ya confirmados',
}

export const ACCION_FILA = {
  alta: 'Nueva',
  actualizacion: 'Actualización',
  sin_cambios: 'Sin cambios',
  error: 'Error',
}

export const ACCION_AUDITORIA = {
  consulta_lista: 'Consultó la lista',
  invitacion_creada: 'Creó la invitación',
  invitacion_editada: 'Editó la invitación',
  invitacion_archivada: 'Archivó la invitación',
  invitacion_restaurada: 'Restauró la invitación',
  desbloqueo: 'Desbloqueó la invitación',
  desbloqueo_retirado: 'Retiró el desbloqueo',
  respuesta_admin: 'Registró una respuesta',
  enlace_generado: 'Generó el enlace',
  enlace_regenerado: 'Regeneró el enlace',
  enlace_revocado: 'Revocó el enlace',
  enlace_consultado: 'Consultó el enlace',
  enlace_marcado_enviado: 'Marcó el enlace como enviado',
  recordatorio_enviado: 'Marcó un recordatorio como enviado',
  importacion: 'Importó un archivo',
  exportacion: 'Exportó la lista',
  purga: 'Borrado programado de datos personales',
}

export const CAMPO = {
  nombre_mostrar: 'Nombre a mostrar',
  adultos: 'Adultos',
  ninos_autorizados: 'Niños autorizados',
  infantes: 'Infantes (menores de 2 años)',
  lado: 'Invitado de',
  grupo: 'Grupo',
  roles: 'Rol en la boda',
  mesa: 'Mesa',
  nota_interna: 'Nota interna',
  no_planner: 'No. de la planner',
  telefono_principal: 'Teléfono principal',
  contacto_alterno_nombre: 'Contacto alterno',
  contacto_alterno_tel: 'Teléfono del contacto alterno',
  hasta: 'Desbloquear hasta',
  confirmados: 'Lugares confirmados',
  alergias: 'Alergias',
  mensaje: 'Mensaje',
  destino: 'Destino',
  lado_por_defecto: 'Lado por defecto',
  filas: 'Filas',
}
