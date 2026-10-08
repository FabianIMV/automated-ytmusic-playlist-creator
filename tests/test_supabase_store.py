"""SupabaseCredentialStore: PostgREST simulado, sin tocar la red."""

from __future__ import annotations

import json

import pytest
import requests
from cryptography.fernet import Fernet

from playlist_creator.core import supabase_store
from playlist_creator.core.supabase_store import SupabaseCredentialStore

URL = "https://proyecto.supabase.co"
ENDPOINT = f"{URL}/rest/v1/ytmusic_credentials"
SECRET_KEY = "sb_secret_abc123"
LEGACY_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.firma"
COOKIE = "SAPISID=super-secreto-123; __Secure-3PSID=otra-cookie-privada"
HEADERS = {"authorization": "SAPISIDHASH 1_abc", "cookie": COOKIE, "x-goog-authuser": "0"}


def make_response(status: int = 200, body=None, text: str | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = (text if text is not None else json.dumps(body if body is not None else [])).encode()
    return response


class FakePostgREST:
    """Tabla en memoria con los tres verbos que usa el store; registra cada llamada."""

    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.calls: list[dict] = []
        self.override: requests.Response | Exception | None = None

    def __call__(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if isinstance(self.override, Exception):
            raise self.override
        if self.override is not None:
            return self.override
        params = kwargs.get("params") or {}
        user_id = params.get("user_id", "").removeprefix("eq.")
        if method == "POST":
            row = kwargs["json"]
            self.rows[row["user_id"]] = row
            return make_response(201, text="")
        if method == "DELETE":
            self.rows.pop(user_id, None)
            return make_response(204, text="")
        if method == "GET":
            row = self.rows.get(user_id)
            return make_response(200, [{"data": row["data"]}] if row else [])
        raise AssertionError(f"método inesperado: {method}")

    @property
    def last(self) -> dict:
        return self.calls[-1]


@pytest.fixture
def fake(monkeypatch) -> FakePostgREST:
    fake = FakePostgREST()
    monkeypatch.setattr(supabase_store.requests, "request", fake)
    return fake


@pytest.fixture
def fernet_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def store(fake, fernet_key) -> SupabaseCredentialStore:
    return SupabaseCredentialStore(URL, SECRET_KEY, fernet_key)


# --- set -----------------------------------------------------------------

def test_set_hace_upsert_con_los_parametros_correctos(fake, store):
    store.set("user-1", HEADERS)

    call = fake.last
    assert call["method"] == "POST"
    assert call["url"] == ENDPOINT
    assert call["params"] == {"on_conflict": "user_id"}
    assert call["headers"]["Prefer"] == "resolution=merge-duplicates"
    assert call["timeout"]
    assert call["json"]["user_id"] == "user-1"
    assert call["json"]["updated_at"]  # se envía siempre: el default de la columna no aplica al actualizar


def test_set_cifra_los_headers_y_no_filtra_nada_en_claro(fake, store, fernet_key):
    store.set("user-1", HEADERS)

    body = fake.last["json"]
    wire = json.dumps(body)
    assert "super-secreto-123" not in wire
    assert "SAPISID" not in wire
    assert "SAPISIDHASH" not in wire
    # Y es un token Fernet que solo se abre con la clave correcta.
    assert json.loads(Fernet(fernet_key).decrypt(body["data"].encode())) == HEADERS


def test_set_dos_veces_reemplaza_la_fila(fake, store):
    store.set("user-1", {"cookie": "a"})
    store.set("user-1", {"cookie": "b"})
    assert store.get("user-1") == {"cookie": "b"}
    assert len(fake.rows) == 1


# --- get -----------------------------------------------------------------

def test_get_consulta_por_user_id_y_descifra(fake, store):
    store.set("user-1", HEADERS)

    assert store.get("user-1") == HEADERS

    call = fake.last
    assert call["method"] == "GET"
    assert call["url"] == ENDPOINT
    assert call["params"] == {"user_id": "eq.user-1", "select": "data", "limit": "1"}


def test_get_sin_fila_devuelve_none(fake, store):
    assert store.get("nadie") is None


def test_get_con_404_devuelve_none(fake, store):
    fake.override = make_response(404, {"code": "PGRST205", "message": "Could not find the table"})
    assert store.get("user-1") is None


def test_get_con_clave_de_cifrado_distinta_devuelve_none(fake, store):
    store.set("user-1", HEADERS)
    otro = SupabaseCredentialStore(URL, SECRET_KEY, Fernet.generate_key())
    assert otro.get("user-1") is None


def test_get_con_dato_corrupto_devuelve_none(fake, store):
    fake.override = make_response(200, [{"data": "esto-no-es-un-token-fernet"}])
    assert store.get("user-1") is None


def test_aislamiento_entre_usuarios(fake, store):
    store.set("a", {"cookie": "de-a"})
    store.set("b", {"cookie": "de-b"})
    assert store.get("a") == {"cookie": "de-a"}
    assert store.get("b") == {"cookie": "de-b"}


# --- delete --------------------------------------------------------------

def test_delete_filtra_por_user_id(fake, store):
    store.set("user-1", HEADERS)
    store.delete("user-1")

    call = fake.last
    assert call["method"] == "DELETE"
    assert call["url"] == ENDPOINT
    assert call["params"] == {"user_id": "eq.user-1"}
    assert store.get("user-1") is None


def test_delete_de_un_usuario_sin_fila_no_falla(fake, store):
    store.delete("nadie")


# --- cabeceras de autenticación -------------------------------------------

def test_clave_nueva_solo_va_en_apikey(fake, fernet_key):
    SupabaseCredentialStore(URL, SECRET_KEY, fernet_key).get("u")
    headers = fake.last["headers"]
    assert headers["apikey"] == SECRET_KEY
    assert "Authorization" not in headers


def test_clave_legacy_jwt_tambien_va_como_bearer(fake, fernet_key):
    SupabaseCredentialStore(URL, LEGACY_KEY, fernet_key).get("u")
    headers = fake.last["headers"]
    assert headers["apikey"] == LEGACY_KEY
    assert headers["Authorization"] == f"Bearer {LEGACY_KEY}"


def test_las_cabeceras_se_envian_en_todas_las_operaciones(fake, fernet_key):
    store = SupabaseCredentialStore(URL, LEGACY_KEY, fernet_key)
    store.set("u", {"cookie": "x"})
    store.get("u")
    store.delete("u")
    assert [c["method"] for c in fake.calls] == ["POST", "GET", "DELETE"]
    assert all(c["headers"]["apikey"] == LEGACY_KEY for c in fake.calls)


def test_la_url_base_tolera_la_barra_final(fake, fernet_key):
    SupabaseCredentialStore(URL + "/", SECRET_KEY, fernet_key).get("u")
    assert fake.last["url"] == ENDPOINT


# --- errores -------------------------------------------------------------

@pytest.mark.parametrize("operation", ["get", "set", "delete"])
def test_error_http_lanza_runtime_error_con_status_y_mensaje(fake, store, operation):
    fake.override = make_response(401, {"message": "Invalid API key", "hint": "revisa la clave"})
    args = {"get": ("u",), "set": ("u", {"cookie": "x"}), "delete": ("u",)}[operation]

    with pytest.raises(RuntimeError, match=r"401.*Invalid API key"):
        getattr(store, operation)(*args)


def test_error_http_sin_json_usa_el_texto(fake, store):
    fake.override = make_response(502, text="Bad Gateway")
    with pytest.raises(RuntimeError, match=r"502.*Bad Gateway"):
        store.get("u")


def test_error_de_red_lanza_runtime_error(fake, store):
    fake.override = requests.ConnectionError("sin conexión")
    with pytest.raises(RuntimeError, match="No se pudo conectar con Supabase"):
        store.set("u", {"cookie": "x"})


def test_timeout_lanza_runtime_error(fake, store):
    fake.override = requests.Timeout("lento")
    with pytest.raises(RuntimeError, match="No se pudo conectar con Supabase"):
        store.get("u")


def test_respuesta_que_no_es_json_lanza_runtime_error(fake, store):
    fake.override = make_response(200, text="<html>no soy json</html>")
    with pytest.raises(RuntimeError, match="no es JSON"):
        store.get("u")


def test_el_error_no_filtra_la_clave_ni_los_datos(fake, store):
    fake.override = make_response(500, {"message": "boom"})
    with pytest.raises(RuntimeError) as exc_info:
        store.set("u", HEADERS)
    assert SECRET_KEY not in str(exc_info.value)
    assert "super-secreto-123" not in str(exc_info.value)


# --- construcción --------------------------------------------------------

def test_clave_fernet_invalida_da_error_claro():
    with pytest.raises(ValueError, match="CREDENTIALS_ENCRYPTION_KEY"):
        SupabaseCredentialStore(URL, SECRET_KEY, "no-es-una-clave-fernet")


@pytest.mark.parametrize("missing", ["url", "key", "encryption"])
def test_faltan_parametros(missing, fernet_key):
    args = {"url": URL, "key": SECRET_KEY, "encryption": fernet_key}
    args[missing] = ""
    with pytest.raises(ValueError):
        SupabaseCredentialStore(args["url"], args["key"], args["encryption"])


def test_acepta_la_clave_de_cifrado_como_bytes(fake):
    key = Fernet.generate_key()
    store = SupabaseCredentialStore(URL, SECRET_KEY, key)
    store.set("u", {"cookie": "x"})
    assert store.get("u") == {"cookie": "x"}


def test_ignora_espacios_alrededor_de_la_url_y_la_clave(fake, fernet_key):
    SupabaseCredentialStore(f" {URL}/\n", f"{LEGACY_KEY}\n", fernet_key).get("u")
    assert fake.last["url"] == ENDPOINT
    assert fake.last["headers"]["apikey"] == LEGACY_KEY
    assert fake.last["headers"]["Authorization"] == f"Bearer {LEGACY_KEY}"
