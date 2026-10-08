"""Tests del núcleo: parseo de credenciales y almacenamiento en archivo (sin red)."""

from __future__ import annotations

import json
import stat

import pytest

from playlist_creator.core.credentials import (
    DEFAULT_HEADERS,
    CredentialsError,
    FileCredentialStore,
    parse_raw_credentials,
)

COOKIE = "SAPISID=abc123; VISITOR_INFO1_LIVE=xyz"

CURL_MULTILINEA = f"""curl 'https://music.youtube.com/youtubei/v1/browse?key=AIza' \\
  -H 'accept: */*' \\
  -H 'authorization: SAPISIDHASH 1700000000_abc' \\
  -H 'x-goog-authuser: 0' \\
  -b '{COOKIE}' \\
  --data-raw '{{"context":{{}}}}'
"""

CURL_DOLLAR_QUOTE = """curl 'https://music.youtube.com/youtubei/v1/browse' \\
  -H 'authorization: SAPISIDHASH 1700000000_abc' \\
  -H $'cookie: SAPISID=abc123; VISITOR_INFO1_LIVE=xyz'
"""


# --- parse_raw_credentials -------------------------------------------------


def test_curl_multilinea_con_barra_invertida_y_cookie_con_b():
    headers = parse_raw_credentials(CURL_MULTILINEA)

    assert headers["authorization"] == "SAPISIDHASH 1700000000_abc"
    assert headers["cookie"] == COOKIE  # -b define la cookie
    assert headers["x-goog-authuser"] == "0"
    # Las claves siempre van en minúsculas
    assert all(k == k.lower() for k in headers)


def test_curl_con_cookie_en_header_y_quoting_dollar_de_chrome():
    headers = parse_raw_credentials(CURL_DOLLAR_QUOTE)

    assert headers["authorization"] == "SAPISIDHASH 1700000000_abc"
    assert headers["cookie"] == COOKIE


def test_formato_clave_valor_en_lineas_ignora_pseudo_headers_http2():
    texto = """accept: */*
:authority: music.youtube.com
authorization: SAPISIDHASH 1_xyz
cookie: SAPISID=abc; otra=1
"""
    headers = parse_raw_credentials(texto)

    assert headers["authorization"] == "SAPISIDHASH 1_xyz"
    assert headers["cookie"] == "SAPISID=abc; otra=1"
    assert not any(k.startswith(":") for k in headers)


def test_json_con_claves_en_mayusculas_se_normaliza():
    texto = json.dumps({"Authorization": "SAPISIDHASH 1_x", "Cookie": "SAPISID=abc", "X-Goog-AuthUser": "0"})
    headers = parse_raw_credentials(texto)

    assert headers["authorization"] == "SAPISIDHASH 1_x"
    assert headers["cookie"] == "SAPISID=abc"
    assert headers["x-goog-authuser"] == "0"


def test_json_invalido_lanza_error():
    with pytest.raises(CredentialsError, match="JSON inválido"):
        parse_raw_credentials('{"authorization": ')


@pytest.mark.parametrize("texto", ["", "   \n  "])
def test_texto_vacio_lanza_error(texto):
    with pytest.raises(CredentialsError, match="vacío"):
        parse_raw_credentials(texto)


def test_falta_authorization_lanza_error():
    with pytest.raises(CredentialsError, match="authorization"):
        parse_raw_credentials("cookie: SAPISID=abc")


def test_falta_cookie_lanza_error():
    with pytest.raises(CredentialsError, match="cookie"):
        parse_raw_credentials("authorization: SAPISIDHASH 1_x")


def test_cookie_sin_sapisid_lanza_error():
    with pytest.raises(CredentialsError, match="SAPISID"):
        parse_raw_credentials("authorization: SAPISIDHASH 1_x\ncookie: VISITOR_INFO1_LIVE=xyz")


def test_se_agregan_defaults_sin_pisar_los_del_usuario():
    texto = """authorization: SAPISIDHASH 1_x
cookie: SAPISID=abc
accept-language: es-CL,es;q=0.9
"""
    headers = parse_raw_credentials(texto)

    # El valor del usuario gana sobre el default
    assert headers["accept-language"] == "es-CL,es;q=0.9"
    # Los defaults que el usuario no envió se agregan
    assert headers["origin"] == DEFAULT_HEADERS["origin"] == "https://music.youtube.com"
    assert headers["x-youtube-client-name"] == DEFAULT_HEADERS["x-youtube-client-name"]
    # El dict de defaults original no se modifica
    assert DEFAULT_HEADERS["accept-language"] == "en-US,en;q=0.9"


# --- FileCredentialStore ---------------------------------------------------


def test_store_set_y_get_ida_y_vuelta(tmp_path):
    store = FileCredentialStore(tmp_path)
    headers = {"authorization": "SAPISIDHASH 1_x", "cookie": "SAPISID=abc"}

    store.set("user-1", headers)

    assert store.get("user-1") == headers


def test_store_get_de_usuario_inexistente_devuelve_none(tmp_path):
    assert FileCredentialStore(tmp_path).get("nadie") is None


def test_store_set_sobrescribe_el_contenido_anterior(tmp_path):
    store = FileCredentialStore(tmp_path)
    store.set("u", {"cookie": "SAPISID=viejo"})
    store.set("u", {"cookie": "SAPISID=nuevo"})

    assert store.get("u") == {"cookie": "SAPISID=nuevo"}


def test_store_delete_elimina_y_tolera_usuario_inexistente(tmp_path):
    store = FileCredentialStore(tmp_path)
    store.set("u", {"cookie": "SAPISID=abc"})

    store.delete("u")
    assert store.get("u") is None

    store.delete("u")  # no debe lanzar
    store.delete("nunca-existio")


def test_store_crea_archivo_con_permisos_600(tmp_path):
    store = FileCredentialStore(tmp_path)
    store.set("u", {"cookie": "SAPISID=abc"})

    path = store._path("u")
    assert path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("user_id", ["../x", "../../../etc/passwd", "/abs/path", "..", "a/b\\c"])
def test_store_user_id_raro_no_escapa_del_directorio(tmp_path, user_id):
    store = FileCredentialStore(tmp_path / "data")
    store.set(user_id, {"cookie": "SAPISID=abc"})

    path = store._path(user_id)
    assert path.resolve().parent == store.dir.resolve()
    assert store.get(user_id) == {"cookie": "SAPISID=abc"}
    # Nada se escribió fuera del directorio de credenciales
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == [path]


def test_store_reescribir_archivo_existente_corrige_permisos(tmp_path):
    store = FileCredentialStore(tmp_path)
    store.set("u", {"cookie": "SAPISID=viejo"})
    path = store._path("u")
    path.chmod(0o644)

    store.set("u", {"cookie": "SAPISID=nuevo"})

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
