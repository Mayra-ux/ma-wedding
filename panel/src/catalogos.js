// Catálogos cerrados (ADR 0017). Deben coincidir con api/app/catalogos.py (lo verifica un test).
export const LADOS = ['Novia', 'Novio', 'Ambos']
export const GRUPOS = ['Familia', 'Amigos', 'Trabajo', 'Otro']
export const ROLES_BODA = [
  'Papás de la novia',
  'Papás del novio',
  'Hermano/a de la novia',
  'Hermano/a del novio',
  'Padrinos de velación',
  'Padrinos de lazo',
  'Padrinos de arras',
  'Padrinos de anillos',
  'Dama de honor',
  'Caballero del novio',
  'Paje',
  'Ofrendas',
  'Otro',
]
export const MOTIVOS_REVISION = [
  'pases_inconsistentes',
  'lado_invalido',
  'grupo_invalido',
  'telefono_invalido',
  'rol_invalido',
]
export const ESTADOS = ['confirmada', 'pendiente', 'no_asiste']
export const MAX_IMPORTACION = 2 * 1024 * 1024 // MAX_IMPORT_FILE de la API
