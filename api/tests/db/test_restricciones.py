"""Restricciones de la DB (doc 02, M1–M14). Cada caso DEBE fallar con el SQLSTATE indicado.

Todo se ejecuta como usuario de EJECUCIÓN y se revierte al final. Datos ficticios.
"""

import pytest
from sqlalchemy import Connection, text

from tests.db.util import falla_con, nueva_invitacion, nueva_version

CHECK, UNIQUE, TOO_LONG, GENERATED = "23514", "23505", "22001", "428C9"


# ------------------------------------------------------------------ invitación
def test_adultos_cero(app_conn: Connection) -> None:  # M1
    falla_con(
        app_conn,
        CHECK,
        "INSERT INTO invitacion (codigo, nombre_mostrar, adultos) VALUES ('INV-001', 'X', 0)",
    )


@pytest.mark.parametrize("columna", ["ninos_autorizados", "infantes"])
def test_negativos(app_conn: Connection, columna: str) -> None:  # M1
    falla_con(
        app_conn,
        CHECK,
        f"INSERT INTO invitacion (codigo, nombre_mostrar, adultos, {columna}) "
        "VALUES ('INV-001', 'X', 1, -1)",
    )


def test_pases_distinto_de_adultos_mas_ninos(app_conn: Connection) -> None:  # M2
    # `pases` es una columna generada: nadie puede escribir un total distinto.
    falla_con(
        app_conn,
        GENERATED,
        "INSERT INTO invitacion (codigo, nombre_mostrar, adultos, ninos_autorizados, pases) "
        "VALUES ('INV-001', 'X', 2, 1, 5)",
    )
    inv = nueva_invitacion(app_conn, adultos=2, ninos_autorizados=1)
    falla_con(app_conn, GENERATED, "UPDATE invitacion SET pases = 5 WHERE id = :i", {"i": inv})
    assert app_conn.scalar(text("SELECT pases FROM invitacion WHERE id = :i"), {"i": inv}) == 3


def test_codigo_duplicado(app_conn: Connection) -> None:  # M3
    nueva_invitacion(app_conn, codigo="INV-001")
    falla_con(
        app_conn,
        UNIQUE,
        "INSERT INTO invitacion (codigo, nombre_mostrar, adultos) VALUES ('INV-001', 'Y', 1)",
    )


@pytest.mark.parametrize("codigo", ["INV-1", "inv-001", "INV-00A", "X-001", "INV-001 "])
def test_codigo_formato(app_conn: Connection, codigo: str) -> None:  # M3
    falla_con(
        app_conn,
        CHECK,
        "INSERT INTO invitacion (codigo, nombre_mostrar, adultos) VALUES (:c, 'X', 1)",
        {"c": codigo},
    )


@pytest.mark.parametrize(
    ("columna", "valor"),
    [("lado", "Primos"), ("lado", "novia"), ("grupo", "Vecinos"), ("grupo", "Familia ")],
)
def test_lado_grupo_fuera_de_catalogo(app_conn: Connection, columna: str, valor: str) -> None:
    falla_con(  # M10
        app_conn,
        CHECK,
        f"INSERT INTO invitacion (codigo, nombre_mostrar, adultos, {columna}) "
        "VALUES ('INV-001', 'X', 1, :v)",
        {"v": valor},
    )


def test_rol_fuera_de_catalogo(app_conn: Connection) -> None:  # M10
    inv = nueva_invitacion(app_conn)
    falla_con(
        app_conn,
        CHECK,
        "INSERT INTO invitacion_rol (invitacion_id, rol) VALUES (:i, 'Testigo')",
        {"i": inv},
    )


def test_rol_repetido(app_conn: Connection) -> None:  # ADR 0017
    inv = nueva_invitacion(app_conn)
    app_conn.execute(
        text("INSERT INTO invitacion_rol VALUES (:i, 'Paje'), (:i, 'Ofrendas')"), {"i": inv}
    )
    falla_con(app_conn, UNIQUE, "INSERT INTO invitacion_rol VALUES (:i, 'Paje')", {"i": inv})


@pytest.mark.parametrize(
    ("tabla", "columna", "maximo"),
    [
        ("invitacion", "nombre_mostrar", 120),
        ("invitacion", "nota_interna", 500),
        ("invitacion", "contacto_alterno_nombre", 120),
        ("version_respuesta", "mensaje", 500),
        ("version_respuesta", "alergias", 200),
    ],
)
def test_longitudes(app_conn: Connection, tabla: str, columna: str, maximo: int) -> None:  # M12
    inv = nueva_invitacion(app_conn)
    exacto, excedido = "á" * maximo, "á" * (maximo + 1)  # cuenta caracteres, no bytes
    if tabla == "invitacion":
        sql = f"UPDATE invitacion SET {columna} = :v WHERE id = :i"
        app_conn.execute(text(sql), {"v": exacto, "i": inv})
        falla_con(app_conn, TOO_LONG, sql, {"v": excedido, "i": inv})
    else:
        sql = (
            "INSERT INTO version_respuesta "
            f"(invitacion_id, numero, vigente, asiste, confirmados, origen, {columna}) "
            "VALUES (:i, :n, false, true, 1, 'invitado', :v)"
        )
        app_conn.execute(text(sql), {"v": exacto, "i": inv, "n": 1})
        falla_con(app_conn, TOO_LONG, sql, {"v": excedido, "i": inv, "n": 2})


def test_nombre_vacio(app_conn: Connection) -> None:
    falla_con(
        app_conn,
        CHECK,
        "INSERT INTO invitacion (codigo, nombre_mostrar, adultos) VALUES ('INV-001', '   ', 1)",
    )


@pytest.mark.parametrize("tel", ["5512345678", "+52 55 " + "1234 5678", "+0" + "123456789", "+1"])
def test_telefono_no_e164(app_conn: Connection, tel: str) -> None:  # M11 (sug.)
    inv = nueva_invitacion(app_conn)
    for columna in ("telefono_principal", "contacto_alterno_tel"):
        falla_con(
            app_conn,
            CHECK,
            f"UPDATE invitacion SET {columna} = :t WHERE id = :i",
            {"t": tel, "i": inv},
        )


def test_telefono_e164_ficticio_valido(app_conn: Connection) -> None:
    # Serie 555-01XX de Norteamérica: reservada para ficción.
    nueva_invitacion(app_conn, telefono_principal="+12025550123")


def test_motivos_revision(app_conn: Connection) -> None:  # M14 (sug.)
    inv = nueva_invitacion(app_conn)
    falla_con(  # texto libre (podría contener datos personales)
        app_conn,
        CHECK,
        "UPDATE invitacion SET requiere_revision = true, "
        "motivos_revision = ARRAY['Llamar a Juan'] WHERE id = :i",
        {"i": inv},
    )
    falla_con(  # marca sin motivo
        app_conn, CHECK, "UPDATE invitacion SET requiere_revision = true WHERE id = :i", {"i": inv}
    )
    falla_con(  # motivo sin marca
        app_conn,
        CHECK,
        "UPDATE invitacion SET motivos_revision = ARRAY['lado_invalido'] WHERE id = :i",
        {"i": inv},
    )
    app_conn.execute(
        text(
            "UPDATE invitacion SET requiere_revision = true, "
            "motivos_revision = ARRAY['pases_inconsistentes'] WHERE id = :i"
        ),
        {"i": inv},
    )


def test_envio_coherente(app_conn: Connection) -> None:  # ADR 0017
    inv = nueva_invitacion(app_conn)
    falla_con(
        app_conn, CHECK, "UPDATE invitacion SET enlace_enviado_en = now() WHERE id = :i", {"i": inv}
    )
    falla_con(
        app_conn,
        CHECK,
        "UPDATE invitacion SET enlace_enviado_en = now(), enlace_enviado_origen = 'sms' "
        "WHERE id = :i",
        {"i": inv},
    )


# ------------------------------------------------------------------ respuestas
def test_dos_versiones_vigentes(app_conn: Connection) -> None:  # M4 / B1
    inv = nueva_invitacion(app_conn)
    nueva_version(app_conn, inv, numero=1)
    falla_con(
        app_conn,
        UNIQUE,
        "INSERT INTO version_respuesta (invitacion_id, numero, vigente, asiste, confirmados, "
        "origen) VALUES (:i, 2, true, true, 1, 'invitado')",
        {"i": inv},
    )


def test_numero_repetido(app_conn: Connection) -> None:
    inv = nueva_invitacion(app_conn)
    nueva_version(app_conn, inv, numero=1, vigente=False)
    falla_con(
        app_conn,
        UNIQUE,
        "INSERT INTO version_respuesta (invitacion_id, numero, vigente, asiste, confirmados, "
        "origen) VALUES (:i, 1, false, true, 1, 'invitado')",
        {"i": inv},
    )


@pytest.mark.parametrize(
    ("asiste", "confirmados", "alergias"),
    [
        (False, 1, None),  # no asiste con confirmados
        (False, 0, "Nueces"),  # no asiste con alergias (ADR 0017: se vacían)
        (True, 0, None),  # asiste con 0
        (True, 1, ""),  # alergias vacías deben ser NULL (sug.)
        (True, 1, "   "),
    ],
)
def test_asistencia_incoherente(
    app_conn: Connection, asiste: bool, confirmados: int, alergias: str | None
) -> None:  # M5
    inv = nueva_invitacion(app_conn)
    falla_con(
        app_conn,
        CHECK,
        "INSERT INTO version_respuesta (invitacion_id, numero, vigente, asiste, confirmados, "
        "alergias, origen) VALUES (:i, 1, true, :a, :c, :al, 'invitado')",
        {"i": inv, "a": asiste, "c": confirmados, "al": alergias},
    )


def test_no_asiste_conserva_mensaje(app_conn: Connection) -> None:  # ADR 0017
    inv = nueva_invitacion(app_conn)
    nueva_version(app_conn, inv, asiste=False, confirmados=0, mensaje="¡Felicidades!")


def test_confirmados_exceden_pases(app_conn: Connection) -> None:  # M5 (disparador)
    inv = nueva_invitacion(app_conn, adultos=2, ninos_autorizados=1)
    nueva_version(app_conn, inv, numero=1, vigente=False, confirmados=3)
    msg = falla_con(
        app_conn,
        CHECK,
        "INSERT INTO version_respuesta (invitacion_id, numero, vigente, asiste, confirmados, "
        "origen) VALUES (:i, 2, true, true, 4, 'invitado')",
        {"i": inv},
    )
    assert "confirmados_exceden_pases" in msg


def test_no_bajar_pases_bajo_confirmados(app_conn: Connection) -> None:  # M6 (disparador)
    inv = nueva_invitacion(app_conn, adultos=3, ninos_autorizados=1)
    nueva_version(app_conn, inv, confirmados=3)
    msg = falla_con(
        app_conn,
        CHECK,
        "UPDATE invitacion SET ninos_autorizados = 0, adultos = 2 WHERE id = :i",
        {"i": inv},
    )
    assert "pases_bajo_confirmados" in msg
    # Bajar hasta exactamente los confirmados sí se permite.
    app_conn.execute(text("UPDATE invitacion SET ninos_autorizados = 0 WHERE id = :i"), {"i": inv})


def test_actor_coherente(app_conn: Connection) -> None:  # B7, C4
    inv = nueva_invitacion(app_conn)
    sql = (
        "INSERT INTO version_respuesta (invitacion_id, numero, vigente, asiste, confirmados, "
        "origen, actor) VALUES (:i, 1, true, true, 1, :o, :a)"
    )
    falla_con(app_conn, CHECK, sql, {"i": inv, "o": "admin", "a": None})
    falla_con(app_conn, CHECK, sql, {"i": inv, "o": "invitado", "a": "novia@ejemplo.invalid"})
    falla_con(app_conn, CHECK, sql, {"i": inv, "o": "planner", "a": None})


@pytest.mark.parametrize(
    "cambio",
    [
        "confirmados = 2",
        "mensaje = 'otro'",
        "asiste = false, confirmados = 0",
        "numero = 9",
        "origen = 'admin', actor = 'x@ejemplo.invalid'",
        "alergias = 'Mariscos'",
    ],
)
def test_version_inmutable(migrator_engine, cambio: str) -> None:  # M9
    # Se prueba como DUEÑO del esquema (sin límite de columnas): el disparador igual lo impide.
    # Para el usuario de ejecución, además, el permiso por columna ya lo bloquea (test_permisos).
    with migrator_engine.connect() as conn, conn.begin():
        inv = nueva_invitacion(conn, adultos=3)
        v = nueva_version(conn, inv, confirmados=1, alergias="Nueces")
        msg = falla_con(
            conn, CHECK, f"UPDATE version_respuesta SET {cambio} WHERE id = :v", {"v": v}
        )
        assert "version_inmutable" in msg
        conn.rollback()


def test_version_cambios_permitidos(app_conn: Connection) -> None:  # M9
    inv = nueva_invitacion(app_conn)
    v = nueva_version(app_conn, inv, alergias="Nueces")
    app_conn.execute(text("UPDATE version_respuesta SET alergias = NULL WHERE id = :v"), {"v": v})
    app_conn.execute(text("UPDATE version_respuesta SET vigente = false WHERE id = :v"), {"v": v})
    falla_con(  # volver a hacerla vigente no
        app_conn, CHECK, "UPDATE version_respuesta SET vigente = true WHERE id = :v", {"v": v}
    )


# ------------------------------------------------------------------ enlaces
def test_dos_enlaces_activos(app_conn: Connection) -> None:  # M7
    inv = nueva_invitacion(app_conn)
    sql = (
        "INSERT INTO enlace (invitacion_id, hmac_token, token_cifrado, id_llave) "
        "VALUES (:i, :h, :c, 'k1')"
    )
    app_conn.execute(text(sql), {"i": inv, "h": b"\x01" * 32, "c": b"\x00" * 50})
    falla_con(app_conn, UNIQUE, sql, {"i": inv, "h": b"\x02" * 32, "c": b"\x00" * 50})
    # Revocado el primero, ya se puede crear otro.
    app_conn.execute(
        text("UPDATE enlace SET revocado_en = now() WHERE invitacion_id = :i"), {"i": inv}
    )
    app_conn.execute(text(sql), {"i": inv, "h": b"\x02" * 32, "c": b"\x00" * 50})


def test_hmac_duplicado_y_longitud(app_conn: Connection) -> None:  # M7, D3
    a, b = nueva_invitacion(app_conn), nueva_invitacion(app_conn)
    sql = (
        "INSERT INTO enlace (invitacion_id, hmac_token, token_cifrado, id_llave) "
        "VALUES (:i, :h, :c, 'k1')"
    )
    app_conn.execute(text(sql), {"i": a, "h": b"\x07" * 32, "c": b"\x00" * 50})
    falla_con(app_conn, UNIQUE, sql, {"i": b, "h": b"\x07" * 32, "c": b"\x00" * 50})
    falla_con(app_conn, CHECK, sql, {"i": b, "h": b"\x08" * 16, "c": b"\x00" * 50})


# ------------------------------------------------------------------ configuración
def test_configuracion_inicial(app_conn: Connection) -> None:  # ADR 0010, 0016
    fila = app_conn.execute(
        text(
            "SELECT cierre_plazo = '2027-02-07T00:00:00-06:00', "
            "congelamiento = '2027-03-07T00:00:00-06:00', "
            "fecha_borrado_1 = '2027-04-05', fecha_borrado_2 = '2027-06-04' "
            "FROM configuracion_evento"
        )
    ).all()
    assert fila == [(True, True, True, True)]


def test_configuracion_unica_y_ordenada(migrator_engine) -> None:
    with migrator_engine.connect() as conn, conn.begin():
        falla_con(
            conn,
            CHECK,
            "INSERT INTO configuracion_evento VALUES (2, now(), now() + interval '1 day', "
            "'2030-01-01', '2030-02-01')",
        )
        falla_con(conn, CHECK, "UPDATE configuracion_evento SET congelamiento = cierre_plazo")
        falla_con(conn, CHECK, "UPDATE configuracion_evento SET fecha_borrado_2 = '2027-04-01'")
        conn.rollback()
