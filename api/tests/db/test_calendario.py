"""Simulación de fechas de I-10 (doc 13): un mismo reloj para la invitación, el panel y la purga.

- 6 feb 2027 00:00: los invitados ya no aceptan cambios (congelada), los novios sí.
- 7 mar 2027 00:00: la planner queda en solo lectura; los novios siguen editando.
- 5 abr 2027: no quedan teléfonos ni alergias, tampoco en el historial.
- 4 jun 2027: no quedan datos personales.
La simulación completa se ejecuta dos veces sobre bases nuevas y da los mismos resultados.
"""

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.estado import MX
from app.purga import contar_tablas, purgar
from tests.db.conftest import APP, borrar_base, crear_base, urls
from tests.db.test_auth_panel import NOVIA, PLANNER, Panel
from tests.db.test_panel_api import LOOKUP, RESPONSE, TEL, Actor, crear, enlace, mover
from tests.db.test_purga import Reloj

S = timedelta(seconds=1)
CONGELA = datetime(2027, 2, 6, 0, 0, tzinfo=MX)
CIERRE_PLANNER = datetime(2027, 3, 7, 0, 0, tzinfo=MX)
BORRADO_1 = datetime(2027, 4, 5, 0, 0, tzinfo=MX)
BORRADO_2 = datetime(2027, 6, 4, 0, 0, tzinfo=MX)


def _purga(engine, ahora: datetime):  # noqa: ANN001, ANN202
    with Session(engine) as s, s.begin():
        return purgar(s, Reloj(ahora))


def _simulacion(engine) -> list[object]:  # noqa: ANN001
    """Recorre el calendario y devuelve lo observado en cada fecha (para comparar corridas)."""
    from tests.db.conftest import RelojFijo

    reloj = RelojFijo()
    panel = Panel(engine, reloj)
    novios, planner = Actor(panel, NOVIA), Actor(panel, PLANNER)
    publico = panel.cliente()
    codigo = crear(novios, adultos=3, telefono_principal=TEL)
    token = enlace(novios, codigo)
    r = publico.post(
        RESPONSE, json={"token": token, "asiste": True, "confirmados": 2, "alergias": "Nueces"}
    )
    assert r.status_code == 200, r.text
    r = publico.post(
        RESPONSE, json={"token": token, "asiste": True, "confirmados": 3, "alergias": "Ninguna"}
    )
    assert r.status_code == 200, r.text
    vistos: list[object] = []

    # ---- 6 feb 00:00: congelamiento de los invitados
    mover(panel, CONGELA - S, novios, planner)
    assert publico.post(LOOKUP, json={"token": token}).json()["estado"] != "congelada"
    mover(panel, CONGELA, novios, planner)
    estado = publico.post(LOOKUP, json={"token": token}).json()["estado"]
    cambio = publico.post(RESPONSE, json={"token": token, "asiste": False, "confirmados": 0})
    assert estado == "congelada" and cambio.status_code == 409
    editar = novios.escribir("PATCH", f"/invitations/{codigo}", {"mesa": 4})
    assert editar.status_code == 200  # los novios no tienen congelamiento
    vistos += [estado, cambio.json()["error"]["code"], editar.status_code]

    # ---- 7 mar 00:00: la planner queda en solo lectura
    mover(panel, CIERRE_PLANNER - S, novios, planner)
    antes = planner.escribir(
        "POST", f"/invitations/{codigo}/reminder/sent", {"destino": "principal"}
    )
    assert antes.status_code == 200
    mover(panel, CIERRE_PLANNER, novios, planner)
    despues = planner.escribir(
        "POST", f"/invitations/{codigo}/reminder/sent", {"destino": "principal"}
    )
    assert despues.status_code == 409
    assert planner.get(f"/invitations/{codigo}").status_code == 200  # sigue leyendo
    respuesta = novios.escribir(
        "PUT", f"/invitations/{codigo}/response", {"asiste": True, "confirmados": 1}
    )
    assert respuesta.status_code == 200  # los novios siguen editando
    vistos += [despues.json()["error"]["code"], respuesta.status_code]

    # ---- 5 abr: teléfonos y alergias, también en el historial
    assert _purga(engine, BORRADO_1 - S).cambios == 0
    p1 = _purga(engine, BORRADO_1)
    with engine.connect() as c:
        telefonos = c.scalar(
            text("SELECT count(*) FROM invitacion WHERE telefono_principal IS NOT NULL")
        )
        alergias = c.scalar(
            text("SELECT count(*) FROM version_respuesta WHERE alergias IS NOT NULL")
        )
        versiones = c.scalar(text("SELECT count(*) FROM version_respuesta"))
    assert (telefonos, alergias) == (0, 0) and versiones == 3  # el historial sigue, sin alergias
    mover(panel, BORRADO_1 + timedelta(hours=1), novios)
    detalle = novios.get(f"/invitations/{codigo}").json()
    assert detalle["telefono_principal"] is None and detalle["alergias"] is None
    historial = novios.get(f"/invitations/{codigo}/history").json()
    assert len(historial) == 3 and all(v.get("alergias") is None for v in historial)
    vistos += [(p1.telefonos, p1.alergias), _purga(engine, BORRADO_1 + S).cambios]

    # ---- 4 jun: no quedan datos personales
    p2 = _purga(engine, BORRADO_2)
    with Session(engine) as s:
        conteos = contar_tablas(s)
    assert conteos == {
        "invitacion": 0,
        "invitacion_rol": 0,
        "version_respuesta": 0,
        "enlace": 0,
        "recordatorio_enviado": 0,
        "sesion_admin": 0,
        "evento_auditoria": 2,  # solo las constancias de la purga (sin datos personales)
        "telefonos": 0,
        "alergias": 0,
    }
    with engine.connect() as c:
        assert set(c.execute(text("SELECT actor, codigo_invitacion FROM evento_auditoria"))) == {
            ("sistema", None)
        }
    mover(panel, BORRADO_2 + timedelta(hours=1), novios)  # la sesión anterior se borró
    assert novios.get("/invitations", params={"incluir_archivadas": True}).json() == []
    assert publico.post(LOOKUP, json={"token": token}).status_code == 404
    vistos += [p2.invitaciones, conteos, _purga(engine, BORRADO_2 + S).cambios]
    return vistos


def test_simulacion_de_fechas_repetible(admin_engine) -> None:  # noqa: ANN001
    from sqlalchemy import create_engine

    from app import migrar

    corridas = []
    for _ in range(2):
        nombre = crear_base(admin_engine)
        u = urls(nombre)
        engine = None
        try:
            migrar.upgrade(u["migrator"], APP)
            engine = create_engine(u["app"])  # usuario de EJECUCIÓN, como la tarea real
            corridas.append(_simulacion(engine))
        finally:
            if engine is not None:
                engine.dispose()
            borrar_base(admin_engine, nombre)
    assert corridas[0] == corridas[1]
