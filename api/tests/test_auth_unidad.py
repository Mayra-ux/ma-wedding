"""Pruebas sin DB del login con Google y las sesiones del panel (I-6). Todo es ficticio."""

import urllib.parse
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.__main__ import claves_con_valor
from app.config import Settings
from app.google import (
    IdentidadNoVerificada,
    desafio_pkce,
    url_autorizacion,
    verificar_id_token,
)
from app.sesiones_panel import (
    OAUTH_VIGENCIA_S,
    EstadoOAuth,
    Listas,
    LlavesPanel,
    Rol,
    SecretoInvalido,
    firmar_estado,
    generar_secreto_sesion,
    leer_estado,
)
from tests.google_simulado import CLIENT_ID, GoogleSimulado, llave_rsa

NONCE = "nonce-de-prueba"


# --------------------------------------------------------------------------- PKCE y URL
def test_pkce_vector_rfc7636() -> None:
    # RFC 7636, apéndice B.
    verificador = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert desafio_pkce(verificador) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_url_de_autorizacion() -> None:
    url = url_autorizacion(CLIENT_ID, "https://api.ejemplo.invalid/cb", "st", "no", "v" * 64)
    partes = urllib.parse.urlsplit(url)
    q = dict(urllib.parse.parse_qsl(partes.query))
    assert f"{partes.scheme}://{partes.netloc}{partes.path}" == (
        "https://accounts.google.com/o/oauth2/v2/auth"
    )
    assert q == {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": "https://api.ejemplo.invalid/cb",
        "scope": "openid email",
        "state": "st",
        "nonce": "no",
        "code_challenge": desafio_pkce("v" * 64),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }


# --------------------------------------------------------------------------- id_token
@pytest.fixture
def google() -> GoogleSimulado:
    return GoogleSimulado()


def _verificar(google: GoogleSimulado, claims: dict) -> str:
    token = google.firmar(claims)
    return verificar_id_token(token, google.llave_publica(token), CLIENT_ID, NONCE).correo


def test_id_token_valido_y_correo_en_minusculas(google: GoogleSimulado) -> None:
    claims = google.claims("Novia.Ficticia@Ejemplo.INVALID", NONCE)
    assert _verificar(google, claims) == "novia.ficticia@ejemplo.invalid"


def test_emisor_sin_esquema_tambien_es_valido(google: GoogleSimulado) -> None:
    claims = google.claims("a@ejemplo.invalid", NONCE, iss="accounts.google.com")
    assert _verificar(google, claims) == "a@ejemplo.invalid"


@pytest.mark.parametrize(
    ("caso", "extra"),
    [
        ("audiencia ajena", {"aud": "otro-cliente.apps.googleusercontent.com"}),
        ("emisor ajeno", {"iss": "https://evil.ejemplo.invalid"}),
        ("vencido", {"exp": 1_000_000_000, "iat": 999_990_000}),
        ("emitido en el futuro", {"iat": 4_000_000_000, "exp": 4_000_003_600}),
        ("nonce distinto", {"nonce": "otro-nonce"}),
        ("sin nonce", {"nonce": ...}),
        ("correo no verificado", {"email_verified": False}),
        ("email_verified como texto", {"email_verified": "true"}),
        ("sin email_verified", {"email_verified": ...}),
        ("sin correo", {"email": ...}),
        ("sin sub", {"sub": ...}),
    ],
)
def test_id_token_rechazado(google: GoogleSimulado, caso: str, extra: dict) -> None:
    with pytest.raises(IdentidadNoVerificada):
        _verificar(google, google.claims("a@ejemplo.invalid", NONCE, **extra))


def test_id_token_firmado_con_otra_llave(google: GoogleSimulado) -> None:
    google.llave_firma = llave_rsa()
    with pytest.raises(IdentidadNoVerificada):
        _verificar(google, google.claims("a@ejemplo.invalid", NONCE))


def test_id_token_hs256_o_none_rechazado(google: GoogleSimulado) -> None:
    import jwt

    claims = google.claims("a@ejemplo.invalid", NONCE)
    for token in (
        jwt.encode(claims, "x" * 32, algorithm="HS256"),
        jwt.encode(claims, None, algorithm="none"),
    ):
        with pytest.raises(IdentidadNoVerificada):
            verificar_id_token(token, google.llave_publica(token), CLIENT_ID, NONCE)


# --------------------------------------------------------------------------- estado de OAuth
LLAVES = LlavesPanel.desde_secreto(generar_secreto_sesion())
ESTADO = EstadoOAuth("st", "no", "v" * 64, 1_000)


def test_estado_firmado_ida_y_vuelta() -> None:
    assert leer_estado(LLAVES, firmar_estado(LLAVES, ESTADO), 1_010) == ESTADO


@pytest.mark.parametrize(
    "valor",
    [
        None,
        "",
        "sin-punto",
        "a.b.c",
        firmar_estado(LLAVES, ESTADO)[:-2] + "xx",  # firma alterada
        "e30." + firmar_estado(LLAVES, ESTADO).split(".")[1],  # carga cambiada
        firmar_estado(LlavesPanel.desde_secreto(generar_secreto_sesion()), ESTADO),  # otra llave
    ],
)
def test_estado_invalido(valor: str | None) -> None:
    assert leer_estado(LLAVES, valor, 1_010) is None


def test_estado_vencido() -> None:
    valor = firmar_estado(LLAVES, ESTADO)
    assert leer_estado(LLAVES, valor, 1_000 + OAUTH_VIGENCIA_S) == ESTADO
    assert leer_estado(LLAVES, valor, 1_000 + OAUTH_VIGENCIA_S + 1) is None
    assert leer_estado(LLAVES, valor, 999) is None  # emitido "en el futuro"


def test_llaves_derivadas_distintas_por_uso() -> None:
    assert LLAVES.oauth != LLAVES.sesion
    assert len(LLAVES.oauth) == len(LLAVES.sesion) == 32


@pytest.mark.parametrize("secreto", ["", "corto", "!!!no-base64!!!", "QUFBQQ"])
def test_session_secret_invalido(secreto: str) -> None:
    with pytest.raises(SecretoInvalido) as info:
        LlavesPanel.desde_secreto(secreto)
    if secreto:
        assert secreto not in str(info.value)


# --------------------------------------------------------------------------- roles y config
def test_roles_por_lista() -> None:
    listas = Listas(
        novios=frozenset({"novia@ejemplo.invalid"}), planner=frozenset({"pl@ejemplo.invalid"})
    )
    assert listas.rol(" Novia@Ejemplo.invalid ") is Rol.ADMIN
    assert listas.rol("pl@ejemplo.invalid") is Rol.LECTOR
    assert listas.rol("intruso@ejemplo.invalid") is None
    assert listas.rol("novia@ejemplo.invalid.otro") is None  # comparación exacta


def test_config_listas_en_minusculas() -> None:
    s = Settings(
        admin_emails_novios=" A@Ejemplo.invalid, b@ejemplo.invalid ,",
        admin_emails_planner="P@ejemplo.invalid",
    )
    assert s.correos_novios() == {"a@ejemplo.invalid", "b@ejemplo.invalid"}
    assert s.correos_planner() == {"p@ejemplo.invalid"}


def test_config_correo_en_ambas_listas_no_arranca() -> None:
    with pytest.raises(ValidationError) as info:
        Settings(admin_emails_novios="x@ejemplo.invalid", admin_emails_planner="X@ejemplo.invalid")
    assert "x@ejemplo.invalid" not in str(info.value).lower()


@pytest.mark.parametrize("valor", ["no-es-correo", "a@b", "a@ejemplo.invalid,mal formado@x.io"])
def test_config_correo_invalido_no_arranca(valor: str) -> None:
    with pytest.raises(ValidationError) as info:
        Settings(admin_emails_novios=valor)
    assert valor not in str(info.value)  # hide_input_in_errors


@pytest.mark.parametrize(
    "origen", ["http://api.ejemplo.invalid", "https://api.ejemplo.invalid/", "ftp://x.io"]
)
def test_config_panel_origin_invalido(origen: str) -> None:
    with pytest.raises(ValidationError):
        Settings(panel_origin=origen)


def test_config_panel_origin_por_defecto() -> None:
    assert Settings().panel_origin == "http://localhost:8000"


# --------------------------------------------------------------------------- generar-llaves
def test_generar_llaves_solo_llena_las_faltantes(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    from app.__main__ import main

    env = tmp_path / ".env"
    env.write_text(
        "TOKEN_HASH_KEY=existente\nTOKEN_ENCRYPTION_KEYS=k1:existente\n"
        "# SESSION_SECRET=__CAMBIAR__\n",
        encoding="utf-8",
    )
    assert main(["generar-llaves", "--env-file", str(env)]) == 0
    texto = env.read_text(encoding="utf-8")
    assert "TOKEN_HASH_KEY=existente" in texto and "TOKEN_ENCRYPTION_KEYS=k1:existente" in texto
    secreto = [ln for ln in texto.splitlines() if ln.startswith("SESSION_SECRET=")][0].split("=")[1]
    LlavesPanel.desde_secreto(secreto)  # válido
    salida = capsys.readouterr().out
    assert secreto not in salida and "existente" not in salida
    assert claves_con_valor(env) == {"TOKEN_HASH_KEY", "TOKEN_ENCRYPTION_KEYS", "SESSION_SECRET"}
    # Una segunda corrida no cambia nada.
    assert main(["generar-llaves", "--env-file", str(env)]) == 0
    assert env.read_text(encoding="utf-8") == texto


def test_lista_de_planner_vacia_es_valida(monkeypatch) -> None:  # noqa: ANN001
    """Sin planner por ahora: `ADMIN_EMAILS_PLANNER=` (vacía) no impide arrancar."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    monkeypatch.setenv("ADMIN_EMAILS_NOVIOS", "novia@ejemplo.invalid")
    monkeypatch.setenv("ADMIN_EMAILS_PLANNER", "")
    s = Settings()
    assert s.correos_planner() == frozenset()
    listas = Listas(novios=s.correos_novios(), planner=s.correos_planner())
    assert listas.rol("novia@ejemplo.invalid") is Rol.ADMIN
    assert listas.rol("planner@ejemplo.invalid") is None  # nadie tiene el rol de planner
    assert TestClient(create_app(s)).get("/health").status_code == 200
