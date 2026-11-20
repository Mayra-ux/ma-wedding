"""Catálogos cerrados (ADR 0017). Deben coincidir con los CHECK de la migración 0001 (test)."""

LADOS = ("Novia", "Novio", "Ambos")
GRUPOS = ("Familia", "Amigos", "Trabajo", "Otro")
ROLES_BODA = (
    "Papás de la novia",
    "Papás del novio",
    "Hermano/a de la novia",
    "Hermano/a del novio",
    "Padrinos de velación",
    "Padrinos de lazo",
    "Padrinos de arras",
    "Padrinos de anillos",
    "Dama de honor",
    "Caballero del novio",
    "Paje",
    "Ofrendas",
    "Otro",
)
MOTIVOS_REVISION = (
    "pases_inconsistentes",
    "lado_invalido",
    "grupo_invalido",
    "telefono_invalido",
    "rol_invalido",
)
