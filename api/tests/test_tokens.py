"""Token, llaves, HMAC y AES-256-GCM (sin DB). Todas las llaves se generan en el test."""

import base64
import pickle
import secrets
from pathlib import Path

import pytest

from app.__main__ import escribir_en_env
from app.config import Settings, validar_origen
from app.tokens import (
    CIFRADO_LEN,
    OCULTO,
    CopiaIlegible,
    LlavesInvalidas,
    LlavesNoConfiguradas,
    armar_url,
    cifrar,
    descifrar,
    generar_llaves_env,
    hmac_token,
    nuevo_token,
    parsear_llaves,
    parsear_token,
)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _llaves(ids: tuple[str, ...] = ("k1",), anterior: bytes | None = None):
    cifrado = ",".join(f"{k}:{_b64(secrets.token_bytes(32))}" for k in ids)
    prev = _b64(anterior) if anterior else None
    return parsear_llaves(_b64(secrets.token_bytes(32)), prev, cifrado)


# ------------------------------------------------------------------ token
def test_token_128_bits_22_caracteres_canonico_y_unico() -> None:
    tokens = [nuevo_token() for _ in range(1000)]
    assert all(len(t.raw) == 16 and len(t.valor) == 22 for t in tokens)
    assert all(parsear_token(t.valor) == t.raw for t in tokens)
    assert len({t.valor for t in tokens}) == 1000


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "corto",
        "A" * 21,
        "A" * 23,
        "A" * 21 + "=",  # relleno
        "A" * 21 + "+",  # alfabeto base64 normal, no url
        "A" * 21 + "/",
        "A" * 20 + "é" + "A",
        "A" * 21 + "B",  # no canónico: bits sobrantes distintos de cero
        None,
        12345,
    ],
)
def test_parsear_token_rechaza(texto: object) -> None:
    assert parsear_token(texto) is None


def test_token_en_claro_oculto_en_repr_str_format_y_pickle() -> None:
    t = nuevo_token()
    for texto in (repr(t), str(t), f"{t}", f"{t!r}", "%s" % t, str([t]), str({"t": t})):  # noqa: UP031
        assert t.valor not in texto
        assert OCULTO in texto
    with pytest.raises(TypeError):
        pickle.dumps(t)


def test_url_del_enlace() -> None:
    t = nuevo_token()
    url = armar_url("https://ma-wedding-six.vercel.app", t)
    assert url == f"https://ma-wedding-six.vercel.app/#t={t.valor}"


# ------------------------------------------------------------------ HMAC y cifrado
def test_hmac_32_bytes_y_depende_de_la_llave() -> None:
    raw = nuevo_token().raw
    a, b = secrets.token_bytes(32), secrets.token_bytes(32)
    assert len(hmac_token(a, raw)) == 32
    assert hmac_token(a, raw) == hmac_token(a, raw)
    assert hmac_token(a, raw) != hmac_token(b, raw)


def test_cifrado_44_bytes_nonce_distinto_e_ida_y_vuelta() -> None:
    llaves = _llaves()
    raw = nuevo_token().raw
    b1, kid = cifrar(llaves, raw, 7)
    b2, _ = cifrar(llaves, raw, 7)
    assert len(b1) == CIFRADO_LEN == 44 and kid == "k1"
    assert b1 != b2  # nonce aleatorio
    assert raw not in b1
    assert descifrar(llaves, b1, 7, kid) == raw


def test_aad_ata_la_copia_a_su_invitacion_y_su_llave() -> None:
    llaves = _llaves(("k2", "k1"))
    raw = nuevo_token().raw
    blob, kid = cifrar(llaves, raw, 7)
    with pytest.raises(CopiaIlegible):
        descifrar(llaves, blob, 8, kid)  # movida a otra invitación
    with pytest.raises(CopiaIlegible):
        descifrar(llaves, blob, 7, "k1")  # id de llave cambiado
    alterada = blob[:-1] + bytes([blob[-1] ^ 1])
    with pytest.raises(CopiaIlegible):
        descifrar(llaves, alterada, 7, kid)
    with pytest.raises(CopiaIlegible):
        descifrar(llaves, blob, 7, "k9")  # llave no configurada


# ------------------------------------------------------------------ llaves
def test_parsear_llaves_y_orden() -> None:
    llaves = _llaves(("k2", "k1"), anterior=secrets.token_bytes(32))
    assert llaves.id_actual == "k2"
    assert list(llaves.cifrado) == ["k2", "k1"]
    assert len(llaves.hashes) == 2
    texto = repr(llaves)
    assert repr(llaves.hash_actual) not in texto
    assert all(repr(v) not in texto for v in llaves.cifrado.values())


@pytest.mark.parametrize(
    ("hash_key", "enc", "error"),
    [
        (None, "k1:" + "A" * 43, LlavesNoConfiguradas),
        ("A" * 43, None, LlavesNoConfiguradas),
        ("A" * 40, "k1:" + "A" * 43, LlavesInvalidas),  # no son 32 bytes
        ("A" * 43, "k1" + "A" * 43, LlavesInvalidas),  # sin id
        ("A" * 43, "K1:" + "A" * 43, LlavesInvalidas),  # id con mayúscula
        ("A" * 43, "k1:" + "A" * 43 + ",k1:" + "B" * 43, LlavesInvalidas),  # id repetido
        ("A" * 43, "k1:###", LlavesInvalidas),
    ],
)
def test_llaves_invalidas_sin_mostrar_valores(hash_key, enc, error) -> None:  # noqa: ANN001
    with pytest.raises(error) as info:
        parsear_llaves(hash_key, None, enc)
    assert "A" * 20 not in str(info.value) and "B" * 20 not in str(info.value)


def test_settings_no_muestra_llaves(monkeypatch: pytest.MonkeyPatch) -> None:
    valores = generar_llaves_env()
    for k, v in valores.items():
        monkeypatch.setenv(k, v)
    s = Settings()
    llave_hash = valores["TOKEN_HASH_KEY"]
    llave_cifrado = valores["TOKEN_ENCRYPTION_KEYS"].split(":", 1)[1]
    for texto in (repr(s), str(s), str(s.model_dump()), repr(s.llaves())):
        assert llave_hash not in texto and llave_cifrado not in texto
    assert s.llaves().id_actual.startswith("k")


def test_generar_llaves_tiene_el_formato_correcto() -> None:
    v = generar_llaves_env()
    llaves = parsear_llaves(v["TOKEN_HASH_KEY"], None, v["TOKEN_ENCRYPTION_KEYS"])
    assert len(llaves.hash_actual) == 32 and len(llaves.cifrado[llaves.id_actual]) == 32
    assert generar_llaves_env() != v


def test_escribir_en_env_no_pisa_llaves_reales(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("POSTGRES_DB=x\nTOKEN_HASH_KEY=__GENERAR__\n", encoding="utf-8")
    escribir_en_env(env, {"TOKEN_HASH_KEY": "uno", "TOKEN_ENCRYPTION_KEYS": "k1:dos"}, False)
    assert env.read_text(encoding="utf-8") == (
        "POSTGRES_DB=x\nTOKEN_HASH_KEY=uno\nTOKEN_ENCRYPTION_KEYS=k1:dos\n"
    )
    with pytest.raises(SystemExit):
        escribir_en_env(env, {"TOKEN_HASH_KEY": "tres"}, False)
    assert "uno" in env.read_text(encoding="utf-8")
    escribir_en_env(env, {"TOKEN_HASH_KEY": "tres"}, True)
    assert "TOKEN_HASH_KEY=tres" in env.read_text(encoding="utf-8")


# ------------------------------------------------------------------ origen
@pytest.mark.parametrize(
    "origen",
    [
        "http://localhost:8080",
        "http://127.0.0.1:8000",
        "https://ma-wedding-six.vercel.app",
        "https://ejemplo.mx",
    ],
)
def test_origen_valido(origen: str) -> None:
    assert validar_origen(origen) == origen


@pytest.mark.parametrize(
    "origen",
    [
        "http://ejemplo.mx",  # http fuera de local
        "https://ejemplo.mx/",
        "https://ejemplo.mx/invitacion",
        "https://ejemplo.mx?x=1",
        "https://ejemplo.mx#t=1",
        "https://usuario:clave@ejemplo.mx",
        "ftp://ejemplo.mx",
        "ejemplo.mx",
        "https://",
    ],
)
def test_origen_invalido(origen: str) -> None:
    with pytest.raises(ValueError):
        validar_origen(origen)
