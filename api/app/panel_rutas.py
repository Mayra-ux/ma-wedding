"""Rutas de /api/v1/admin (I-7; contrato 07 §7.2, ADR 0026 y 0027).

Todas pasan por `guardia_admin` (app/panel.py):
- Lecturas: novios y planner, salvo las marcadas `solo_novios` (el enlace en claro).
- Escrituras: solo novios, salvo las marcadas `permite_planner` (marcar un recordatorio).
- Los novios no tienen congelamiento (ADR 0027).

Ninguna respuesta incluye el token ni la URL del enlace, salvo `GET …/link` (solo novios).
"""

from fastapi import FastAPI, Request, Response

from app import invitaciones as svc
from app.enlaces import (
    ErrorEnlace,
    generar_enlace,
    obtener_enlace,
    regenerar_enlace,
    revocar_enlace,
)
from app.errores import ErrorAPI
from app.esquemas_panel import (
    EntradaDesbloqueo,
    EntradaEdicion,
    EntradaEnlaceEnviado,
    EntradaInvitacion,
    EntradaRecordatorio,
    EntradaRespuestaAdmin,
)
from app.estado import iso_mx

SOLO_NOVIOS = {"solo_novios": True}
PERMITE_PLANNER = {"permite_planner": True}


def registrar_rutas(app: FastAPI) -> None:  # noqa: C901 (lista plana de rutas)
    def ctx(request: Request):  # noqa: ANN202
        return request.app.state.panel

    def actor(request: Request) -> str:
        return request.state.usuario.correo

    def sesion(request: Request):  # noqa: ANN202
        c = ctx(request)
        if c.sesiones is None:
            raise ErrorAPI(503, "auth_no_configurada")
        return c.sesiones()

    def llaves(request: Request):  # noqa: ANN202
        c = ctx(request)
        if c.llaves_tokens is None:
            raise RuntimeError("llaves de tokens no configuradas")
        return c.llaves_tokens

    # ------------------------------------------------------------------ lectura (N y P)
    @app.get("/invitations")
    def listar(request: Request, incluir_archivadas: bool = False) -> list[dict]:
        with sesion(request) as s, s.begin():
            filas = svc.lista(s, incluir_archivadas)
            # La consulta de la lista queda en la auditoría, sin datos personales (ADR 0026).
            svc.auditar(
                s,
                actor(request),
                "consulta_lista",
                detalle={"incluir_archivadas": incluir_archivadas, "filas": len(filas)},
            )
        return filas

    @app.get("/summary")
    def resumen(request: Request) -> dict:
        with sesion(request) as s, s.begin():
            return svc.resumen(svc.lista(s, incluir_archivadas=False))

    @app.get("/invitations/{codigo}")
    def ver(request: Request, codigo: str) -> dict:
        with sesion(request) as s, s.begin():
            return svc.detalle(s, codigo)

    @app.get("/invitations/{codigo}/history")
    def historial(request: Request, codigo: str) -> list[dict]:
        with sesion(request) as s, s.begin():
            return svc.historial(s, codigo)

    @app.get("/audit")
    def auditoria(request: Request) -> list[dict]:
        with sesion(request) as s, s.begin():
            return svc.auditoria(s)

    @app.get("/config")
    def config(request: Request) -> dict:
        with sesion(request) as s, s.begin():
            return svc.config_publica(s)

    @app.get("/invitations/{codigo}/reminder")
    def recordatorio(request: Request, codigo: str, destino: str = "principal") -> dict:
        if destino not in ("principal", "alterno"):
            raise ErrorAPI(422, "validacion", {"destino": "fuera_de_catalogo"})
        with sesion(request) as s, s.begin():
            r = svc.recordatorio(s, codigo, destino, ctx(request).reloj())
        return {"tipo": r.tipo, "texto": r.texto, "telefono": r.telefono, "wa_url": r.wa_url}

    # ------------------------------------------------------------------ escritura de la planner
    @app.post("/invitations/{codigo}/reminder/sent", openapi_extra=PERMITE_PLANNER)
    def recordatorio_enviado(request: Request, codigo: str, entrada: EntradaRecordatorio) -> dict:
        with sesion(request) as s, s.begin():
            tipo = svc.marcar_recordatorio(
                s, codigo, entrada.destino, ctx(request).reloj(), actor(request)
            )
        return {"tipo": tipo, "destino": entrada.destino}

    # ------------------------------------------------------------------ invitaciones (solo N)
    @app.post("/invitations", status_code=201)
    def crear(request: Request, entrada: EntradaInvitacion) -> dict:
        with sesion(request) as s, s.begin():
            inv = svc.crear(s, entrada, actor(request))
            codigo = inv.codigo
        return {"codigo": codigo}

    @app.patch("/invitations/{codigo}")
    def editar(request: Request, codigo: str, entrada: EntradaEdicion) -> dict:
        with sesion(request) as s, s.begin():
            svc.editar(s, codigo, entrada, actor(request))
            return svc.detalle(s, codigo)

    @app.post("/invitations/{codigo}/archive")
    def archivar(request: Request, codigo: str) -> dict:
        with sesion(request) as s, s.begin():
            svc.archivar(s, codigo, actor(request))
            return svc.detalle(s, codigo)

    @app.post("/invitations/{codigo}/restore")
    def restaurar(request: Request, codigo: str) -> dict:
        with sesion(request) as s, s.begin():
            svc.restaurar(s, codigo, actor(request))
            return svc.detalle(s, codigo)

    @app.post("/invitations/{codigo}/unlock")
    def desbloquear(request: Request, codigo: str, entrada: EntradaDesbloqueo) -> dict:
        with sesion(request) as s, s.begin():
            svc.desbloquear(s, codigo, entrada.hasta, ctx(request).reloj(), actor(request))
        return {"desbloqueada_hasta": iso_mx(entrada.hasta)}

    @app.delete("/invitations/{codigo}/unlock")
    def retirar_desbloqueo(request: Request, codigo: str) -> dict:
        with sesion(request) as s, s.begin():
            svc.retirar_desbloqueo(s, codigo, actor(request))
        return {"desbloqueada_hasta": None}

    @app.put("/invitations/{codigo}/response")
    def responder(request: Request, codigo: str, entrada: EntradaRespuestaAdmin) -> dict:
        with sesion(request) as s, s.begin():
            v = svc.responder_como_admin(s, codigo, entrada, actor(request))
            return {
                "numero": v.numero,
                "asiste": v.asiste,
                "confirmados": v.confirmados,
                "alergias": v.alergias,
                "mensaje": v.mensaje,
                "origen": v.origen,
                "actor": v.actor,
                "creada_en": iso_mx(v.creada_en),
            }

    # ------------------------------------------------------------------ enlaces (solo N)
    def _enlace(funcion, request: Request, codigo: str, accion: str):  # noqa: ANN001, ANN202
        with sesion(request) as s, s.begin():
            inv = svc.buscar(s, codigo)
            try:
                resultado = funcion(s, inv.id)
            except ErrorEnlace as exc:
                raise ErrorAPI(exc.status, exc.codigo) from None
            svc.auditar(s, actor(request), accion, codigo)  # nunca el token
            enviado = (iso_mx(inv.enlace_enviado_en), inv.enlace_enviado_origen)
        return resultado, enviado

    @app.get("/invitations/{codigo}/link", openapi_extra=SOLO_NOVIOS)
    def ver_enlace(request: Request, codigo: str) -> dict:
        resultado, (enviado_en, origen) = _enlace(
            lambda s, i: obtener_enlace(s, i, llaves(request), ctx(request).invitation_origin),
            request,
            codigo,
            "enlace_consultado",
        )
        return {
            "url": resultado.url,
            "enlace_enviado_en": enviado_en,
            "enlace_enviado_origen": origen,
        }

    @app.post("/invitations/{codigo}/link", status_code=201)
    def generar(request: Request, codigo: str) -> dict:
        resultado, _ = _enlace(
            lambda s, i: generar_enlace(s, i, llaves(request), ctx(request).invitation_origin),
            request,
            codigo,
            "enlace_generado",
        )
        return {"url": resultado.url}

    @app.post("/invitations/{codigo}/link/regenerate", status_code=201)
    def regenerar(request: Request, codigo: str) -> dict:
        resultado, _ = _enlace(
            lambda s, i: regenerar_enlace(s, i, llaves(request), ctx(request).invitation_origin),
            request,
            codigo,
            "enlace_regenerado",
        )
        return {"url": resultado.url}

    @app.post("/invitations/{codigo}/link/revoke", status_code=204)
    def revocar(request: Request, codigo: str) -> Response:
        _enlace(revocar_enlace, request, codigo, "enlace_revocado")
        return Response(status_code=204)

    @app.post("/invitations/{codigo}/link/sent")
    def enlace_enviado(request: Request, codigo: str, entrada: EntradaEnlaceEnviado) -> dict:
        with sesion(request) as s, s.begin():
            svc.marcar_enlace_enviado(
                s, codigo, entrada.origen, ctx(request).reloj(), actor(request)
            )
            inv = svc.buscar(s, codigo)
            return {
                "enlace_enviado_en": iso_mx(inv.enlace_enviado_en),
                "enlace_enviado_origen": inv.enlace_enviado_origen,
            }
