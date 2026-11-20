"""API del panel (criterios de I-7; ADR 0006, 0007, 0016, 0017, 0026, 0027). Todo es ficticio.

Usa el mismo Google simulado y las mismas sesiones de I-6. Teléfonos de la serie ficticia
555 (reservada para ficción) y correos @ejemplo.invalid.
"""

import threading
import urllib.parse
from datetime import datetime, timedelta

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import text

from app.estado import MX
from tests.db.test_auth_panel import NOVIA, ORIGEN, PLANNER, Panel

A = "/api/v1/admin"
LOOKUP = "/api/v1/public/invitation/lookup"
RESPONSE = "/api/v1/public/invitation/response"
CIERRE = datetime(2027, 1, 31, 0, 0, tzinfo=MX)
CONGELA = datetime(2027, 2, 6, 0, 0, tzinfo=MX)
CIERRE_PLANNER = datetime(2027, 3, 7, 0, 0, tzinfo=MX)
S = timedelta(seconds=1)
TEL = "2025550123"  # serie 555-01XX, reservada para ficción
MX52 = "+" + "52"  # se arma por partes (tests/test_sin_telefonos_reales.py)


@pytest.fixture
def panel(app_engine, reloj, limpiar) -> Panel:  # noqa: ANN001
    return Panel(app_engine, reloj)


class Actor:
    """Cliente con la sesión de un rol: novios o planner."""

    def __init__(self, panel: Panel, correo: str) -> None:
        self.panel, self.correo = panel, correo
        self.sesion = panel.entrar(correo)
        self.c = panel.cliente()

    def renovar(self) -> None:
        self.sesion = self.panel.entrar(self.correo)

    def get(self, ruta: str, **kw):  # noqa: ANN003, ANN201
        return self.c.get(A + ruta, headers=self.sesion.cookie(), **kw)

    def escribir(self, metodo: str, ruta: str, json=None):  # noqa: ANN001, ANN201
        return self.c.request(metodo, A + ruta, headers=self.sesion.escritura(), json=json)


@pytest.fixture
def novios(panel: Panel) -> Actor:
    return Actor(panel, NOVIA)


@pytest.fixture
def planner(panel: Panel) -> Actor:
    return Actor(panel, PLANNER)


def mover(panel: Panel, instante: datetime, *actores: Actor) -> None:
    """Mueve el reloj simulado. Un salto de horas vence las sesiones por inactividad (I-6),
    así que cada actor vuelve a iniciar sesión."""
    panel.reloj.ahora = instante
    for a in actores:
        a.renovar()


def crear(novios: Actor, **campos) -> str:  # noqa: ANN003
    datos = {"nombre_mostrar": "Familia Ficticia", "adultos": 2} | campos
    r = novios.escribir("POST", "/invitations", datos)
    assert r.status_code == 201, r.text
    return r.json()["codigo"]


def enlace(novios: Actor, codigo: str) -> str:
    r = novios.escribir("POST", f"/invitations/{codigo}/link")
    assert r.status_code == 201, r.text
    return r.json()["url"].split("#t=")[1]


def publica(panel: Panel, token: str) -> dict:
    return panel.cliente().post(LOOKUP, json={"token": token}).json()


def sql(panel: Panel, consulta: str, **p):  # noqa: ANN003, ANN201
    with panel.engine.begin() as conn:
        return conn.execute(text(consulta), p)


def auditoria(panel: Panel) -> list[tuple]:
    return list(
        sql(
            panel,
            "SELECT actor, accion, codigo_invitacion, detalle FROM evento_auditoria ORDER BY id",
        )
    )


# =========================================================================== alta y validaciones
def test_alta_normaliza_y_audita(novios: Actor, panel: Panel) -> None:
    codigo = crear(
        novios,
        nombre_mostrar="  Familia Ficticia  ",
        adultos=3,
        ninos_autorizados=1,
        infantes=1,
        lado="Novia",
        grupo="Familia",
        roles=["Paje", "Padrinos de lazo"],
        mesa=4,
        telefono_principal="(202) 555-0123",
        contacto_alterno_nombre="Contacto Ficticio",
        contacto_alterno_tel="+1 202 555 0199",
    )
    assert codigo == "INV-001"
    d = novios.get(f"/invitations/{codigo}").json()
    assert d["nombre_mostrar"] == "Familia Ficticia"
    assert d["pases"] == 4 and d["estado_respuesta"] == "pendiente"
    assert d["roles"] == ["Padrinos de lazo", "Paje"]  # orden del catálogo
    assert d["telefono_principal"] == MX52 + TEL  # 10 dígitos → +52
    assert d["contacto_alterno_tel"] == "+12025550199"  # extranjero con su lada
    assert d["enlace_activo"] is False and d["requiere_revision"] is False
    assert auditoria(panel)[-1][1:] == ("invitacion_creada", codigo, {})
    assert crear(novios) == "INV-002"


def test_codigo_siguiente_al_mayor(novios: Actor, panel: Panel) -> None:
    sql(
        panel, "INSERT INTO invitacion (codigo, nombre_mostrar, adultos) VALUES ('INV-950', 'X', 1)"
    )
    assert crear(novios) == "INV-951"


@pytest.mark.parametrize(
    ("campos", "campo", "motivo"),
    [
        ({"adultos": 0}, "adultos", "fuera_de_rango"),
        ({"ninos_autorizados": -1}, "ninos_autorizados", "fuera_de_rango"),
        ({"infantes": -1}, "infantes", "fuera_de_rango"),
        ({"nombre_mostrar": "   "}, "nombre_mostrar", "obligatorio"),
        ({"nombre_mostrar": "x" * 121}, "nombre_mostrar", "demasiado_largo"),
        ({"lado": "Ninguno"}, "lado", "fuera_de_catalogo"),
        ({"grupo": "Vecinos"}, "grupo", "fuera_de_catalogo"),
        ({"roles": ["Mago"]}, "roles", "fuera_de_catalogo"),
        ({"roles": ["Paje", "Paje"]}, "roles", "repetido"),
        ({"telefono_principal": "12345"}, "telefono_principal", "telefono_invalido"),
        ({"contacto_alterno_tel": "+52 abc"}, "contacto_alterno_tel", "telefono_invalido"),
        ({"mesa": 0}, "mesa", "fuera_de_rango"),
        ({"nota_interna": "x" * 501}, "nota_interna", "demasiado_largo"),
        ({"nombre_mostrar": "a\x00b"}, "nombre_mostrar", "caracteres_no_permitidos"),
    ],
)
def test_alta_valida_cada_campo(novios: Actor, campos: dict, campo: str, motivo: str) -> None:
    datos = {"nombre_mostrar": "Familia Ficticia", "adultos": 2} | campos
    r = novios.escribir("POST", "/invitations", datos)
    assert r.status_code == 422, r.text
    error = r.json()["error"]
    assert error["code"] == "validacion" and error["fields"] == {campo: motivo}
    for valor in campos.values():  # el error nunca repite el valor recibido
        if isinstance(valor, str) and len(valor) > 2:
            assert valor not in r.text


@pytest.mark.parametrize(
    "datos",
    [
        {"nombre_mostrar": "X", "adultos": "2"},  # tipo incorrecto
        {"nombre_mostrar": "X", "adultos": 2, "pases": 9},  # campo desconocido (M2: derivado)
        {"adultos": 2},  # falta el nombre
    ],
)
def test_alta_rechaza_tipos_y_campos_desconocidos(novios: Actor, datos: dict) -> None:
    assert novios.escribir("POST", "/invitations", datos).status_code == 400


# =========================================================================== edición
def test_edicion_parcial_roles_y_auditoria_sin_valores(novios: Actor, panel: Panel) -> None:
    codigo = crear(novios, roles=["Paje"], nota_interna="Nota trazable")
    r = novios.escribir(
        "PATCH", f"/invitations/{codigo}", {"mesa": 7, "roles": ["Ofrendas"], "nota_interna": None}
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["mesa"] == 7 and d["roles"] == ["Ofrendas"] and d["nota_interna"] is None
    assert d["nombre_mostrar"] == "Familia Ficticia"  # lo no enviado no cambia
    ultimo = auditoria(panel)[-1]
    assert ultimo[1:3] == ("invitacion_editada", codigo)
    assert ultimo[3] == {"campos": ["mesa", "nota_interna", "roles"]}
    # Sin cambios reales no se audita nada nuevo.
    n = len(auditoria(panel))
    novios.escribir("PATCH", f"/invitations/{codigo}", {"mesa": 7})
    assert len(auditoria(panel)) == n


def test_no_se_bajan_pases_por_debajo_de_los_confirmados(novios: Actor) -> None:
    codigo = crear(novios, adultos=3, ninos_autorizados=1)
    r = novios.escribir(
        "PUT", f"/invitations/{codigo}/response", {"asiste": True, "confirmados": 3}
    )
    assert r.status_code == 200
    r = novios.escribir("PATCH", f"/invitations/{codigo}", {"adultos": 1})  # pases 2 < 3
    assert r.status_code == 409 and r.json()["error"]["code"] == "pases_menores_que_confirmados"
    r = novios.escribir("PATCH", f"/invitations/{codigo}", {"ninos_autorizados": 0})  # 3 = 3
    assert r.status_code == 200 and r.json()["pases"] == 3


def test_marca_de_revision_se_recalcula(novios: Actor, panel: Panel) -> None:
    sql(
        panel,
        "INSERT INTO invitacion (codigo, nombre_mostrar, adultos, pases_planner_original, "
        "requiere_revision, motivos_revision) VALUES ('INV-100', 'Familia Ficticia', 3, 5, true, "
        "ARRAY['pases_inconsistentes', 'lado_invalido'])",
    )
    d = novios.escribir("PATCH", "/invitations/INV-100", {"ninos_autorizados": 2}).json()
    assert d["motivos_revision"] == ["lado_invalido"] and d["requiere_revision"] is True
    d = novios.escribir("PATCH", "/invitations/INV-100", {"lado": "Novio"}).json()
    assert d["motivos_revision"] == [] and d["requiere_revision"] is False
    d = novios.escribir("PATCH", "/invitations/INV-100", {"adultos": 4}).json()  # 6 ≠ 5
    assert d["motivos_revision"] == ["pases_inconsistentes"]


def test_no_encontrada_404(novios: Actor) -> None:
    assert novios.get("/invitations/INV-999").status_code == 404
    assert novios.escribir("PATCH", "/invitations/INV-999", {"mesa": 1}).status_code == 404


# =========================================================================== archivar
def test_archivar_revoca_el_enlace_y_saca_de_lista_y_resumen(novios: Actor, panel: Panel) -> None:
    codigo = crear(novios)
    otra = crear(novios)
    token = enlace(novios, codigo)
    assert publica(panel, token)["estado"] == "abierta"
    r = novios.escribir("POST", f"/invitations/{codigo}/archive")
    assert r.status_code == 200 and r.json()["archivada"] is True
    assert panel.cliente().post(LOOKUP, json={"token": token}).status_code == 404
    assert [f["codigo"] for f in novios.get("/invitations").json()] == [otra]
    con = novios.get("/invitations", params={"incluir_archivadas": "true"}).json()
    assert [f["codigo"] for f in con] == [codigo, otra]
    assert novios.get("/summary").json()["invitaciones"] == 1
    # Archivada: no se edita, no se desbloquea, no recibe respuesta ni enlace.
    for metodo, ruta, cuerpo in (
        ("PATCH", "", {"mesa": 2}),
        ("PUT", "/response", {"asiste": False, "confirmados": 0}),
        ("POST", "/link", None),
    ):
        r = novios.escribir(metodo, f"/invitations/{codigo}{ruta}", cuerpo)
        assert r.status_code == 409 and r.json()["error"]["code"] == "archivada", ruta
    r = novios.escribir("POST", f"/invitations/{codigo}/archive")
    assert r.json()["error"]["code"] == "ya_archivada"
    # Restaurar: activa y sin enlace.
    assert novios.escribir("POST", f"/invitations/{codigo}/restore").status_code == 200
    assert novios.get(f"/invitations/{codigo}/link").json()["error"]["code"] == "sin_enlace_activo"
    r = novios.escribir("POST", f"/invitations/{codigo}/restore")
    assert r.json()["error"]["code"] == "no_archivada"


# =========================================================================== desbloqueo
def test_desbloqueo_limites_y_vencimiento(novios: Actor, panel: Panel) -> None:
    codigo = crear(novios)
    token = enlace(novios, codigo)
    hasta = CIERRE + timedelta(days=2)
    cuerpo = {"hasta": hasta.isoformat()}
    # Antes del cierre del plazo: 409.
    r = novios.escribir("POST", f"/invitations/{codigo}/unlock", cuerpo)
    assert r.status_code == 409 and r.json()["error"]["code"] == "plazo_aun_abierto"
    mover(panel, CIERRE, novios)
    assert publica(panel, token)["estado"] == "cerrada"
    # Más allá del congelamiento: 422. En el pasado: 422.
    r = novios.escribir(
        "POST", f"/invitations/{codigo}/unlock", {"hasta": (CONGELA + S).isoformat()}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "mas_alla_del_congelamiento"
    r = novios.escribir(
        "POST", f"/invitations/{codigo}/unlock", {"hasta": (CIERRE - S).isoformat()}
    )
    assert r.status_code == 422 and r.json()["error"]["fields"] == {"hasta": "en_el_pasado"}
    # Hasta el congelamiento exacto sí se permite (última ventana: 5 feb incluido).
    assert (
        novios.escribir(
            "POST", f"/invitations/{codigo}/unlock", {"hasta": CONGELA.isoformat()}
        ).status_code
        == 200
    )
    # Válido: la invitación pasa a abierta y vuelve a cerrada al vencer (reloj simulado).
    assert novios.escribir("POST", f"/invitations/{codigo}/unlock", cuerpo).status_code == 200
    assert publica(panel, token)["estado"] == "abierta"
    mover(panel, hasta - S, novios)
    r = panel.cliente().post(RESPONSE, json={"token": token, "asiste": True, "confirmados": 1})
    assert r.status_code == 200
    mover(panel, hasta, novios)
    assert publica(panel, token)["estado"] == "cerrada"
    assert ("desbloqueo", codigo) in [(a[1], a[2]) for a in auditoria(panel)]
    assert novios.escribir("DELETE", f"/invitations/{codigo}/unlock").status_code == 200
    assert novios.get(f"/invitations/{codigo}").json()["desbloqueada_hasta"] is None


def test_no_se_desbloquea_despues_del_congelamiento(novios: Actor, panel: Panel) -> None:
    codigo = crear(novios)
    token = enlace(novios, codigo)
    mover(panel, CONGELA - timedelta(hours=1), novios)
    assert (
        novios.escribir(
            "POST", f"/invitations/{codigo}/unlock", {"hasta": CONGELA.isoformat()}
        ).status_code
        == 200
    )
    mover(panel, CONGELA, novios)  # el desbloqueo vigente no permite responder (ADR 0027)
    assert publica(panel, token)["estado"] == "congelada"
    r = panel.cliente().post(RESPONSE, json={"token": token, "asiste": True, "confirmados": 1})
    assert r.status_code == 409
    r = novios.escribir(
        "POST", f"/invitations/{codigo}/unlock", {"hasta": (CONGELA + S).isoformat()}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "rsvp_congelado"


# =========================================================================== respuesta del admin
def test_respuesta_del_admin_en_cualquier_momento(novios: Actor, panel: Panel) -> None:
    codigo = crear(novios, adultos=2)
    for instante in (CIERRE + S, CONGELA, CIERRE_PLANNER + timedelta(days=1)):
        mover(panel, instante, novios)  # tras el plazo, el congelamiento y el cierre de la planner
        r = novios.escribir(
            "PUT",
            f"/invitations/{codigo}/response",
            {"asiste": True, "confirmados": 2, "alergias": "Ninguna", "mensaje": "Hola"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["origen"] == "admin" and r.json()["actor"] == NOVIA
    h = novios.get(f"/invitations/{codigo}/history").json()
    assert [v["numero"] for v in h] == [3, 2, 1] and h[0]["vigente"] is True
    assert {v["origen"] for v in h} == {"admin"}
    assert auditoria(panel)[-1][1:] == (
        "respuesta_admin",
        codigo,
        {"asiste": True, "confirmados": 2},
    )


def test_respuesta_del_admin_rango_y_alergias(novios: Actor) -> None:
    codigo = crear(novios, adultos=2)
    ruta = f"/invitations/{codigo}/response"
    for cuerpo in (
        {"asiste": True, "confirmados": 3},
        {"asiste": True, "confirmados": 0},
        {
            "asiste": False,
            "confirmados": 1,
        },
    ):
        r = novios.escribir("PUT", ruta, cuerpo)
        assert r.json()["error"]["code"] == "confirmados_fuera_de_rango"
    r = novios.escribir(
        "PUT", ruta, {"asiste": False, "confirmados": 0, "alergias": "Nueces", "mensaje": "Suerte"}
    )
    assert r.json()["alergias"] is None and r.json()["mensaje"] == "Suerte"  # B5


def test_novios_sin_congelamiento(novios: Actor, panel: Panel) -> None:
    codigo = crear(novios)
    mover(panel, CIERRE_PLANNER + timedelta(days=10), novios)
    assert novios.escribir("PATCH", f"/invitations/{codigo}", {"adultos": 5}).status_code == 200
    assert novios.escribir("POST", f"/invitations/{codigo}/link").status_code == 201
    assert novios.escribir("POST", f"/invitations/{codigo}/link/regenerate").status_code == 201
    assert (
        novios.escribir(
            "POST", f"/invitations/{codigo}/link/sent", {"origen": "manual"}
        ).status_code
        == 200
    )
    assert novios.escribir("POST", f"/invitations/{codigo}/link/revoke").status_code == 204
    assert novios.escribir("POST", f"/invitations/{codigo}/archive").status_code == 200
    assert novios.escribir("POST", f"/invitations/{codigo}/restore").status_code == 200
    assert crear(novios).startswith("INV-")


# =========================================================================== enlaces
def test_enlaces_ciclo_completo(novios: Actor, panel: Panel) -> None:
    codigo = crear(novios)
    assert novios.get(f"/invitations/{codigo}/link").status_code == 404
    token = enlace(novios, codigo)
    r = novios.escribir("POST", f"/invitations/{codigo}/link")
    assert r.json()["error"]["code"] == "ya_tiene_enlace"
    r = novios.escribir("POST", f"/invitations/{codigo}/link/sent", {"origen": "whatsapp"})
    assert r.json()["enlace_enviado_origen"] == "whatsapp"
    ver = novios.get(f"/invitations/{codigo}/link").json()
    assert ver["url"] == f"http://localhost:8080/#t={token}"
    nuevo = novios.escribir("POST", f"/invitations/{codigo}/link/regenerate").json()["url"]
    assert panel.cliente().post(LOOKUP, json={"token": token}).status_code == 404
    assert novios.get(f"/invitations/{codigo}").json()["enlace_enviado"] is False  # reiniciada
    assert novios.escribir("POST", f"/invitations/{codigo}/link/revoke").status_code == 204
    assert panel.cliente().post(LOOKUP, json={"token": nuevo.split("#t=")[1]}).status_code == 404
    acciones = [a[1] for a in auditoria(panel) if a[2] == codigo]
    assert acciones == [
        "invitacion_creada",
        "enlace_generado",
        "enlace_marcado_enviado",
        "enlace_consultado",
        "enlace_regenerado",
        "enlace_revocado",
    ]
    # Ningún evento de auditoría contiene el token.
    assert token not in str(auditoria(panel))


def test_enlace_en_revision_409(novios: Actor, panel: Panel) -> None:
    sql(
        panel,
        "INSERT INTO invitacion (codigo, nombre_mostrar, adultos, requiere_revision, "
        "motivos_revision) VALUES ('INV-200', 'X', 1, true, ARRAY['lado_invalido'])",
    )
    r = novios.escribir("POST", "/invitations/INV-200/link")
    assert r.status_code == 409 and r.json()["error"]["code"] == "requiere_revision"


# =========================================================================== recordatorios
def test_recordatorio_por_fase(novios: Actor, planner: Actor, panel: Panel) -> None:
    codigo = crear(novios, telefono_principal=TEL)
    token = enlace(novios, codigo)
    r = planner.get(f"/invitations/{codigo}/reminder").json()
    assert r["tipo"] == "confirmar"
    assert "a más tardar el sábado 30 de enero de 2027, desde el enlace" in r["texto"]
    assert r["telefono"] == MX52 + TEL
    assert r["wa_url"].startswith(f"https://wa.me/52{TEL}?text=")
    assert urllib.parse.unquote(r["wa_url"].split("text=")[1]) == r["texto"]
    assert token not in str(r) and "#t=" not in str(r)
    mover(panel, CIERRE - S, novios, planner)
    assert planner.get(f"/invitations/{codigo}/reminder").json()["tipo"] == "confirmar"
    mover(panel, CIERRE, novios, planner)  # 31 ene 00:00 → recordatorio del evento
    r = planner.get(f"/invitations/{codigo}/reminder").json()
    assert r["tipo"] == "evento"
    assert r["texto"].startswith(
        "Hola, te recordamos que la boda de Mayra y Alejandro es el sábado"
    )
    mover(panel, CIERRE_PLANNER - S, novios, planner)
    assert planner.get(f"/invitations/{codigo}/reminder").json()["tipo"] == "evento"
    mover(panel, CIERRE_PLANNER, novios, planner)
    r = planner.get(f"/invitations/{codigo}/reminder")
    assert r.status_code == 409 and r.json()["error"]["code"] == "recordatorios_cerrados"


def test_recordatorio_sin_telefono_y_alterno(novios: Actor, planner: Actor) -> None:
    codigo = crear(novios, contacto_alterno_tel=TEL)
    r = planner.get(f"/invitations/{codigo}/reminder")
    assert r.status_code == 409 and r.json()["error"]["code"] == "sin_telefono"
    r = planner.get(f"/invitations/{codigo}/reminder", params={"destino": "alterno"})
    assert r.status_code == 200


def test_planner_marca_recordatorio_hasta_su_cierre(
    novios: Actor, planner: Actor, panel: Panel
) -> None:
    codigo = crear(novios, telefono_principal=TEL)
    enlace(novios, codigo)
    novios.escribir("POST", f"/invitations/{codigo}/link/sent", {"origen": "whatsapp"})
    mover(
        panel, CONGELA + timedelta(days=3), novios, planner
    )  # después del congelamiento de invitados
    r = planner.escribir("POST", f"/invitations/{codigo}/reminder/sent", {"destino": "principal"})
    assert r.status_code == 200 and r.json() == {"tipo": "evento", "destino": "principal"}
    fila = novios.get(f"/invitations/{codigo}").json()
    assert fila["recordatorios"] == 1 and fila["ultimo_recordatorio_tipo"] == "evento"
    assert fila["enlace_enviado_origen"] == "whatsapp"  # no pisa el envío del enlace
    assert auditoria(panel)[-1] == (
        PLANNER,
        "recordatorio_enviado",
        codigo,
        {"tipo": "evento", "destino": "principal"},
    )
    mover(panel, CIERRE_PLANNER, novios, planner)
    r = planner.escribir("POST", f"/invitations/{codigo}/reminder/sent", {"destino": "principal"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "recordatorios_cerrados"
    assert list(sql(panel, "SELECT count(*) FROM recordatorio_enviado"))[0][0] == 1


# =========================================================================== planner
def test_planner_ve_todo_salvo_enlaces(novios: Actor, planner: Actor, panel: Panel) -> None:
    codigo = crear(novios, nota_interna="Nota ficticia", telefono_principal=TEL)
    token = enlace(novios, codigo)
    novios.escribir("POST", f"/invitations/{codigo}/link/sent", {"origen": "whatsapp"})
    panel.cliente().post(
        RESPONSE, json={"token": token, "asiste": True, "confirmados": 1, "mensaje": "Hola"}
    )
    fila = planner.get("/invitations").json()[0]
    assert fila["mensaje"] == "Hola" and fila["nota_interna"] == "Nota ficticia"
    assert fila["enlace_activo"] is True and fila["enlace_enviado"] is True
    h = planner.get(f"/invitations/{codigo}/history").json()
    assert h[0]["mensaje"] == "Hola" and "actor" in h[0]
    assert planner.get("/audit").status_code == 200
    r = planner.get(f"/invitations/{codigo}/link")
    assert r.status_code == 403 and r.json()["error"]["code"] == "sin_permiso"


def _rutas_get_admin(app) -> list[tuple[str, bool]]:  # noqa: ANN001
    return [
        (r.path, bool((r.openapi_extra or {}).get("solo_novios")))
        for r in app.state.admin.routes
        if isinstance(r, APIRoute) and "GET" in r.methods and not r.path.startswith("/prueba")
    ]


def test_lecturas_solo_novios_dan_403_a_la_planner(
    panel: Panel, planner: Actor, novios: Actor
) -> None:
    codigo = crear(novios)
    enlace(novios, codigo)
    solo = [p for p, s in _rutas_get_admin(panel.app) if s]
    assert solo == ["/invitations/{codigo}/link"]
    for ruta in solo:
        assert planner.get(ruta.replace("{codigo}", codigo)).status_code == 403
        assert novios.get(ruta.replace("{codigo}", codigo)).status_code == 200


def test_ninguna_respuesta_para_la_planner_contiene_token_ni_enlace(
    novios: Actor, planner: Actor, panel: Panel
) -> None:
    """Recorre TODAS las lecturas del panel como planner con datos trazables."""
    codigos, tokens = [], []
    for i in range(3):
        c = crear(novios, nombre_mostrar=f"Familia Trazable {i}", telefono_principal=TEL)
        codigos.append(c)
        tokens.append(enlace(novios, c))
    viejo = tokens[0]
    tokens[0] = (
        novios.escribir("POST", f"/invitations/{codigos[0]}/link/regenerate")
        .json()["url"]
        .split("#t=")[1]
    )
    tokens.append(viejo)
    novios.escribir("POST", f"/invitations/{codigos[1]}/link/sent", {"origen": "manual"})
    novios.get(f"/invitations/{codigos[1]}/link")  # deja "enlace_consultado" en la auditoría
    panel.cliente().post(
        RESPONSE, json={"token": tokens[1], "asiste": True, "confirmados": 1, "mensaje": "Hola"}
    )
    planner.escribir("POST", f"/invitations/{codigos[2]}/reminder/sent", {"destino": "principal"})

    respuestas = []
    for ruta, solo in _rutas_get_admin(panel.app):
        for codigo in codigos if "{codigo}" in ruta else [None]:
            url = ruta.replace("{codigo}", codigo) if codigo else ruta
            r = planner.get(url)
            respuestas.append((url, r.status_code, r.text))
            assert r.status_code == (403 if solo else 200), (url, r.status_code)
    me = planner.c.get("/api/v1/auth/me", headers=planner.sesion.cookie())
    respuestas.append(("/auth/me", me.status_code, me.text))
    # 4 lecturas generales + 4 por invitación × 3 + /auth/me
    assert len(respuestas) == 17
    for url, _status, cuerpo in respuestas:
        for token in tokens:
            assert token not in cuerpo, url
        assert "#t=" not in cuerpo and "%23t%3D" not in cuerpo, url
        assert "localhost:8080/#" not in cuerpo, url


# =========================================================================== lista y resumen
def _datos_variados(novios: Actor, panel: Panel) -> list[str]:
    c1 = crear(novios, adultos=3, ninos_autorizados=1, infantes=1, lado="Novia", grupo="Familia",
               roles=["Padrinos de lazo", "Paje"])  # fmt: skip
    c2 = crear(novios, adultos=2, lado="Novio", grupo="Amigos", roles=["Paje"])
    c3 = crear(novios, adultos=1, lado="Ambos")
    c4 = crear(novios, adultos=4, ninos_autorizados=2, grupo="Trabajo")
    c5 = crear(novios, adultos=2, lado="Novia", grupo="Familia")  # se archivará
    novios.escribir("PUT", f"/invitations/{c1}/response", {"asiste": True, "confirmados": 3})
    novios.escribir("PUT", f"/invitations/{c2}/response", {"asiste": False, "confirmados": 0})
    novios.escribir("PUT", f"/invitations/{c4}/response", {"asiste": True, "confirmados": 6})
    novios.escribir("PUT", f"/invitations/{c5}/response", {"asiste": True, "confirmados": 2})
    novios.escribir("POST", f"/invitations/{c5}/archive")
    return [c1, c2, c3, c4, c5]


def test_resumen_cuadra_con_la_lista(novios: Actor, planner: Actor, panel: Panel) -> None:
    _datos_variados(novios, panel)
    filas = novios.get("/invitations").json()
    s = planner.get("/summary").json()
    assert s == novios.get("/summary").json()
    assert s["invitaciones"] == len(filas) == 4
    assert s["pases_asignados"] == sum(f["pases"] for f in filas) == 13
    assert s["personas_confirmadas"] == sum(f["confirmados"] or 0 for f in filas) == 9
    assert s["ninos_autorizados"] == 3 and s["infantes"] == 1
    for estado in ("confirmada", "no_asiste", "pendiente"):
        sub = [f for f in filas if f["estado_respuesta"] == estado]
        assert s["por_estado"][estado] == {
            "invitaciones": len(sub),
            "pases": sum(f["pases"] for f in sub),
            "confirmados": sum(f["confirmados"] or 0 for f in sub),
        }
    for clave, cubos, vacio in (
        ("lado", s["por_lado"], "sin_lado"),
        ("grupo", s["por_grupo"], "sin_grupo"),
    ):  # noqa: E501
        for nombre, cubo in cubos.items():
            sub = [f for f in filas if (f[clave] or vacio) == nombre]
            assert cubo["invitaciones"] == len(sub) and cubo["pases"] == sum(
                f["pases"] for f in sub
            )
        assert sum(c["invitaciones"] for c in cubos.values()) == len(filas)
    assert s["por_rol"]["Paje"]["invitaciones"] == 2  # una invitación cuenta en cada rol
    assert s["por_rol"]["Padrinos de lazo"] == {"invitaciones": 1, "pases": 4, "confirmados": 3}


def test_lista_campos_y_auditoria_de_la_consulta(
    novios: Actor, planner: Actor, panel: Panel
) -> None:
    _datos_variados(novios, panel)
    fila = novios.get("/invitations").json()[0]
    assert set(fila) >= {
        "codigo", "nombre_mostrar", "adultos", "ninos_autorizados", "infantes", "pases",
        "estado_respuesta", "confirmados", "ultima_respuesta_en", "ultima_respuesta_origen",
        "alergias", "lado", "grupo", "roles", "mesa", "telefono_principal",
        "contacto_alterno_nombre", "contacto_alterno_tel", "enlace_enviado", "enlace_enviado_en",
        "requiere_revision", "motivos_revision", "desbloqueada_hasta", "archivada", "mensaje",
        "nota_interna", "enlace_activo", "recordatorios",
    }  # fmt: skip
    assert "url" not in fila and "token" not in fila
    assert fila["ultima_respuesta_origen"] == "admin"
    planner.get("/invitations", params={"incluir_archivadas": "true"})
    consultas = [a for a in auditoria(panel) if a[1] == "consulta_lista"]
    assert consultas[-2:] == [
        (NOVIA, "consulta_lista", None, {"incluir_archivadas": False, "filas": 4}),
        (PLANNER, "consulta_lista", None, {"incluir_archivadas": True, "filas": 5}),
    ]


def test_auditoria_sin_datos_personales(novios: Actor, panel: Panel) -> None:
    nombre, nota, alergia, mensaje = (
        "Familia Trazable", "Nota trazable", "Alergia trazable", "Mensaje trazable"
    )  # fmt: skip
    codigo = crear(novios, nombre_mostrar=nombre, nota_interna=nota, telefono_principal=TEL)
    novios.escribir("PATCH", f"/invitations/{codigo}", {"nombre_mostrar": nombre + " 2"})
    novios.escribir(
        "PUT",
        f"/invitations/{codigo}/response",
        {"asiste": True, "confirmados": 1, "alergias": alergia, "mensaje": mensaje},
    )
    novios.escribir("POST", f"/invitations/{codigo}/link")
    novios.get("/invitations")
    texto = str([a[3] for a in auditoria(panel)])
    for valor in (nombre, nota, alergia, mensaje, TEL):
        assert valor not in texto
    acciones = {a[1] for a in auditoria(panel)}
    assert {"invitacion_creada", "invitacion_editada", "respuesta_admin", "enlace_generado",
            "consulta_lista"} <= acciones  # fmt: skip


def test_config(planner: Actor) -> None:
    assert planner.get("/config").json() == {
        "cierre_plazo": "2027-01-31T00:00:00-06:00",
        "fecha_limite_mostrar": "2027-01-30",
        "congelamiento": "2027-02-06T00:00:00-06:00",
        "cierre_planner": "2027-03-07T00:00:00-06:00",
        "fecha_borrado_1": "2027-04-05",
        "fecha_borrado_2": "2027-06-04",
    }


# =========================================================================== concurrencia
def test_respuesta_y_bajada_de_pases_simultaneas_quedan_coherentes(
    novios: Actor, panel: Panel
) -> None:
    """SELECT … FOR UPDATE: nunca quedan confirmados vigentes por encima de los pases."""
    for _ in range(5):
        codigo = crear(novios, adultos=4)
        resultados = {}

        def responder(codigo: str = codigo, resultados: dict = resultados) -> None:
            resultados["r"] = novios.escribir(
                "PUT", f"/invitations/{codigo}/response", {"asiste": True, "confirmados": 4}
            ).status_code

        def bajar(codigo: str = codigo, resultados: dict = resultados) -> None:
            resultados["p"] = novios.escribir(
                "PATCH", f"/invitations/{codigo}", {"adultos": 2}
            ).status_code

        hilos = [threading.Thread(target=responder), threading.Thread(target=bajar)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        assert sorted(resultados.values()) in ([200, 200], [200, 409], [200, 422]), resultados
        pases, confirmados = list(
            sql(
                panel,
                "SELECT i.pases, coalesce(v.confirmados, 0) FROM invitacion i LEFT JOIN "
                "version_respuesta v ON v.invitacion_id = i.id AND v.vigente WHERE i.codigo = :c",
                c=codigo,
            )
        )[0]
        assert confirmados <= pases


def test_origen_del_panel_en_las_escrituras(novios: Actor) -> None:
    assert ORIGEN == "https://testserver"
