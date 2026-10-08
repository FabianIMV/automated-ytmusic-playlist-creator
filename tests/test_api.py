"""API FastAPI con TestClient y un MusicClient falso (sin red)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient

from playlist_creator.api import auth
from playlist_creator.api.main import create_app
from playlist_creator.config import Settings
from playlist_creator.core import supabase_store
from playlist_creator.core.credentials import DEFAULT_HEADERS, FileCredentialStore
from playlist_creator.core.supabase_store import SupabaseCredentialStore
from playlist_creator.models import Privacy, Track

SUPABASE_URL = "https://proyecto.supabase.co"
JWT_SECRET = "secreto-hs256-de-prueba-con-largo-suficiente-123"
ISSUER = f"{SUPABASE_URL}/auth/v1"

CURL = (
    "curl 'https://music.youtube.com/youtubei/v1/browse?prettyPrint=false' \\\n"
    "  -H 'accept: */*' \\\n"
    "  -H 'authorization: SAPISIDHASH 1700000000_deadbeef' \\\n"
    "  -H 'cookie: SAPISID=abc123; __Secure-3PSID=cookie-privada' \\\n"
    "  -H 'x-goog-authuser: 0' \\\n"
    "  --data-raw '{}'"
)
STORED_HEADERS = {"authorization": "SAPISIDHASH 1_x", "cookie": "SAPISID=abc123; __Secure-3PSID=otra"}

ENV_VARS = (
    "AUTH_MODE SUPABASE_URL SUPABASE_JWT_SECRET SUPABASE_JWT_AUDIENCE CREDENTIAL_STORE SUPABASE_SERVICE_KEY "
    "CREDENTIALS_ENCRYPTION_KEY DATA_DIR LEGACY_HEADERS_FILE CORS_ORIGINS FRONTEND_DIST BATCH_SIZE "
    "BATCH_DELAY_SECONDS JOB_WORKERS MAX_SONGS_PER_JOB YTMUSIC_LANGUAGE"
).split()


# --- Doble de YouTube Music -------------------------------------------------

def make_track(video_id: str, title: str, artist: str) -> Track:
    return Track(video_id=video_id, title=title, artists=[artist], result_type="song")


CATALOG = {
    "Oasis - Wonderwall": make_track("vid-wonderwall", "Wonderwall", "Oasis"),
    "Oasis - Live Forever": make_track("vid-liveforever", "Live Forever", "Oasis"),
    "Oasis - Supersonic": make_track("vid-supersonic", "Supersonic", "Oasis"),
}


class FakeMusic:
    """MusicClient en memoria que registra lo que la API le pide."""

    def __init__(self, existing: dict[str, set[str]] | None = None):
        self.catalog = dict(CATALOG)
        self.existing = existing or {}
        self.reject_account: str | None = None
        self.fail_create: str | None = None
        self.fail_add: str | None = None
        self.factory_calls: list[dict[str, str] | None] = []
        self.searches: list[str] = []
        self.created: list[tuple[str, str, Privacy]] = []
        self.added: list[tuple[str, list[str]]] = []

    def factory(self, headers: dict[str, str] | None) -> "FakeMusic":
        self.factory_calls.append(headers)
        return self

    def search_track(self, query: str) -> Track | None:
        self.searches.append(query)
        return self.catalog.get(query)

    def create_playlist(self, name: str, description: str, privacy: Privacy) -> str:
        if self.fail_create:
            raise RuntimeError(self.fail_create)
        self.created.append((name, description, privacy))
        return "PLnueva"

    def get_playlist_video_ids(self, playlist_id: str) -> set[str]:
        return set(self.existing.get(playlist_id, set()))

    def add_items(self, playlist_id: str, video_ids: list[str]) -> None:
        if self.fail_add:
            raise RuntimeError(self.fail_add)
        self.added.append((playlist_id, list(video_ids)))

    def account_info(self) -> dict[str, Any]:
        if self.reject_account:
            raise RuntimeError(self.reject_account)
        return {"accountName": "Ana", "channelHandle": "@ana", "accountPhotoUrl": "https://img.example/ana.jpg"}


# --- Fixtures y helpers -----------------------------------------------------

@dataclass
class Env:
    client: TestClient
    music: FakeMusic
    app: FastAPI
    settings: Settings


def make_settings(tmp_path, **overrides) -> Settings:
    values: dict[str, Any] = {
        "auth_mode": "none",
        "credential_store": "file",
        "supabase_url": None,
        "supabase_jwt_secret": None,
        "supabase_service_key": None,
        "credentials_encryption_key": None,
        "data_dir": tmp_path,
        "legacy_headers_file": tmp_path / "no.json",
        "frontend_dist": tmp_path / "sin-frontend",
        "batch_delay_seconds": 0,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def api_clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def api_build(tmp_path):
    """Crea una app lista para usar (con lifespan activo) y la cierra al terminar el test."""
    clients: list[TestClient] = []

    def build(music: FakeMusic | None = None, store=None, **settings_overrides) -> Env:
        music = music or FakeMusic()
        settings = make_settings(tmp_path, **settings_overrides)
        app = create_app(settings, credential_store=store, client_factory=music.factory)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return Env(client=client, music=music, app=app, settings=settings)

    yield build
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def api_env(api_build) -> Env:
    return api_build()


def connect(env: Env, user_id: str = "local", headers: dict[str, str] | None = None) -> None:
    env.app.state.credential_store.set(user_id, headers or STORED_HEADERS)


def wait_for_job(client: TestClient, job_id: str, headers: dict[str, str] | None = None, timeout: float = 5) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}", headers=headers).json()
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(0.01)
    raise AssertionError(f"El job {job_id} no terminó a tiempo")


def songs_source(*songs: str) -> dict:
    return {"type": "songs", "songs": list(songs)}


# --- Salud y usuario ----------------------------------------------------------

def test_health(api_env):
    response = api_env.client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["auth_mode"] == "none"
    assert body["version"]


def test_me_local_desconectado(api_env):
    body = api_env.client.get("/api/me").json()
    assert body["user"]["id"] == "local"
    assert body["auth_mode"] == "none"
    assert body["ytmusic"] == {"connected": False, "account": None, "error": None}
    assert api_env.music.factory_calls == []  # sin credenciales no se consulta a YouTube Music


def test_me_local_conectado(api_env):
    connect(api_env)

    body = api_env.client.get("/api/me").json()

    assert body["ytmusic"]["connected"] is True
    assert body["ytmusic"]["account"] == {"name": "Ana", "handle": "@ana", "photo_url": "https://img.example/ana.jpg"}
    assert api_env.music.factory_calls == [STORED_HEADERS]


def test_me_con_credenciales_vencidas_informa_el_motivo(api_env):
    connect(api_env)
    api_env.music.reject_account = "sesión vencida"

    ytmusic = api_env.client.get("/api/me").json()["ytmusic"]

    assert ytmusic["connected"] is False
    assert "sesión vencida" in ytmusic["error"]


# --- Credenciales de YouTube Music ---------------------------------------------

def test_guardar_credenciales_con_curl_valido(api_env):
    response = api_env.client.put("/api/ytmusic/credentials", json={"raw": CURL})

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["account"]["name"] == "Ana"

    saved = api_env.app.state.credential_store.get("local")
    assert saved["authorization"] == "SAPISIDHASH 1700000000_deadbeef"
    assert "SAPISID=abc123" in saved["cookie"]
    assert saved["x-goog-authuser"] == "0"
    assert saved["origin"] == DEFAULT_HEADERS["origin"]  # se completan los headers por defecto
    assert api_env.music.factory_calls == [saved]  # se validó con los mismos headers que se guardaron


def test_la_api_nunca_devuelve_las_credenciales(api_env):
    put = api_env.client.put("/api/ytmusic/credentials", json={"raw": CURL})
    get = api_env.client.get("/api/ytmusic/credentials")
    me = api_env.client.get("/api/me")

    for response in (put, get, me):
        assert "deadbeef" not in response.text
        assert "cookie-privada" not in response.text
        assert "SAPISID" not in response.text


def test_estado_de_credenciales(api_env):
    assert api_env.client.get("/api/ytmusic/credentials").json()["connected"] is False
    api_env.client.put("/api/ytmusic/credentials", json={"raw": CURL})
    assert api_env.client.get("/api/ytmusic/credentials").json()["connected"] is True


@pytest.mark.parametrize(
    "raw, motivo",
    [
        ("esto no es un cURL ni son headers", "Faltan headers"),
        ("curl 'https://music.youtube.com' -H 'accept: */*'", "Faltan headers"),
        ("curl 'https://music.youtube.com' -H 'authorization: SAPISIDHASH 1_x' -H 'cookie: a=b'", "SAPISID"),
        ("{esto no es json", "JSON"),
    ],
)
def test_credenciales_invalidas_dan_422_y_no_se_guardan(api_env, raw, motivo):
    response = api_env.client.put("/api/ytmusic/credentials", json={"raw": raw})

    assert response.status_code == 422
    assert motivo in response.json()["detail"]
    assert api_env.app.state.credential_store.get("local") is None
    assert api_env.music.factory_calls == []  # ni siquiera se intenta con YouTube Music


def test_credenciales_demasiado_cortas_dan_422(api_env):
    assert api_env.client.put("/api/ytmusic/credentials", json={"raw": "x"}).status_code == 422
    assert api_env.client.put("/api/ytmusic/credentials", json={}).status_code == 422


def test_credenciales_rechazadas_por_youtube_music_dan_422_y_no_se_guardan(api_env):
    api_env.music.reject_account = "HTTP 401"

    response = api_env.client.put("/api/ytmusic/credentials", json={"raw": CURL})

    assert response.status_code == 422
    assert "rechazó" in response.json()["detail"]
    assert "HTTP 401" in response.json()["detail"]
    assert api_env.app.state.credential_store.get("local") is None


def test_rechazo_no_pisa_las_credenciales_que_ya_funcionaban(api_env):
    connect(api_env)
    api_env.music.reject_account = "HTTP 401"

    assert api_env.client.put("/api/ytmusic/credentials", json={"raw": CURL}).status_code == 422

    assert api_env.app.state.credential_store.get("local") == STORED_HEADERS


def test_borrar_credenciales(api_env):
    connect(api_env)

    response = api_env.client.delete("/api/ytmusic/credentials")

    assert response.status_code == 204
    assert response.content == b""
    assert api_env.app.state.credential_store.get("local") is None
    assert api_env.client.get("/api/ytmusic/credentials").json()["connected"] is False
    # Es idempotente
    assert api_env.client.delete("/api/ytmusic/credentials").status_code == 204


# --- Setlists ---------------------------------------------------------------

SETLISTFM_URL = "https://www.setlist.fm/setlist/the-hives/2025/teatro-caupolican-santiago-chile-1234abcd.html"
SETLISTFM_HTML = """
<html><head>
  <meta property="og:title" content="The Hives Setlist at Teatro Caupolicán, Santiago, Chile on March 3, 2025 | setlist.fm">
</head><body>
  <a class="url fn" href="/venue/teatro-caupolican">Teatro Caupolicán</a>
  <em class="link">Mar 3, 2025</em>
  <ol class="songsList">
    <li><a class="songLabel" href="/stats/songs/hate">Hate to Say I Told You So</a></li>
    <li><a class="songLabel" href="/stats/songs/main">Main Offender</a></li>
    <li><a class="songLabel" href="/stats/songs/intro">(Intro)</a></li>
  </ol>
</body></html>
"""


def fake_http_response(html: str, status: int = 200) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = html.encode("utf-8")
    return response


@pytest.fixture
def api_setlistfm(monkeypatch):
    """Reemplaza requests.get dentro de core.sources y registra las llamadas."""
    state = SimpleNamespace(calls=[], html=SETLISTFM_HTML, error=None, status=200)

    def fake_get(url, **kwargs):
        state.calls.append((url, kwargs))
        if state.error:
            raise state.error
        return fake_http_response(state.html, state.status)

    monkeypatch.setattr("playlist_creator.core.sources.requests.get", fake_get)
    return state


def test_parse_texto_ignora_comentarios_y_lineas_vacias(api_env):
    text = "# Mi setlist\n\nOasis - Wonderwall\n   \n  # otro comentario\n  Oasis - Live Forever  \n"

    response = api_env.client.post("/api/setlists/parse", json={"type": "text", "text": text})

    assert response.status_code == 200
    body = response.json()
    assert body["songs"] == ["Oasis - Wonderwall", "Oasis - Live Forever"]
    assert body["artist"] == "Oasis"
    assert body["event_info"] is None
    assert body["suggested_name"] == "Oasis - Concert Setlist"
    assert "2 songs" in body["suggested_description"]


def test_parse_lista_de_canciones(api_env):
    response = api_env.client.post("/api/setlists/parse", json=songs_source("Blur - Song 2", "", "# nada"))

    assert response.status_code == 200
    assert response.json()["songs"] == ["Blur - Song 2"]
    assert response.json()["artist"] == "Blur"


def test_parse_no_toca_youtube_music(api_env):
    api_env.client.post("/api/setlists/parse", json=songs_source("Blur - Song 2"))
    assert api_env.music.factory_calls == []
    assert api_env.music.searches == []


def test_parse_setlistfm(api_env, api_setlistfm):
    response = api_env.client.post("/api/setlists/parse", json={"type": "setlistfm", "url": SETLISTFM_URL})

    assert response.status_code == 200
    body = response.json()
    assert body["artist"] == "The Hives"
    assert body["event_info"] == "Teatro Caupolicán - Mar 3, 2025"
    assert body["songs"] == ["The Hives - Hate to Say I Told You So", "The Hives - Main Offender"]  # sin "(Intro)"
    assert body["suggested_name"] == "The Hives - Concert Setlist"
    assert api_setlistfm.calls[0][0] == SETLISTFM_URL
    assert "User-Agent" in api_setlistfm.calls[0][1]["headers"]


def test_parse_setlistfm_con_error_de_red_da_422(api_env, api_setlistfm):
    api_setlistfm.error = requests.ConnectionError("sin red")

    response = api_env.client.post("/api/setlists/parse", json={"type": "setlistfm", "url": SETLISTFM_URL})

    assert response.status_code == 422
    assert "No se pudo descargar el setlist" in response.json()["detail"]


def test_parse_setlistfm_con_http_error_da_422(api_env, api_setlistfm):
    api_setlistfm.status = 404

    response = api_env.client.post("/api/setlists/parse", json={"type": "setlistfm", "url": SETLISTFM_URL})

    assert response.status_code == 422
    assert "No se pudo descargar el setlist" in response.json()["detail"]


def test_parse_setlistfm_sin_canciones_da_422(api_env, api_setlistfm):
    api_setlistfm.html = "<html><body><p>nada por aquí</p></body></html>"

    response = api_env.client.post("/api/setlists/parse", json={"type": "setlistfm", "url": SETLISTFM_URL})

    assert response.status_code == 422
    assert "no contiene canciones" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "setlistfm", "url": "https://ejemplo.com/setlist/x"},
        {"type": "setlistfm", "url": "https://www.setlist.fm.evil.com/x"},
        {"type": "desconocido", "text": "Oasis - Wonderwall"},
        {"type": "text", "text": ""},
        {"type": "songs", "songs": []},
    ],
)
def test_parse_fuentes_invalidas_dan_422(api_env, api_setlistfm, payload):
    response = api_env.client.post("/api/setlists/parse", json=payload)
    assert response.status_code == 422
    assert api_setlistfm.calls == []  # nunca se descarga una URL que no es de setlist.fm


def test_parse_solo_comentarios_da_422(api_env):
    response = api_env.client.post("/api/setlists/parse", json={"type": "text", "text": "# uno\n\n# dos"})
    assert response.status_code == 422
    assert "no contiene canciones" in response.json()["detail"]


def test_parse_respeta_el_maximo_de_canciones(api_build):
    env = api_build(max_songs_per_job=2)

    ok = env.client.post("/api/setlists/parse", json=songs_source("A - 1", "A - 2"))
    too_many = env.client.post("/api/setlists/parse", json=songs_source("A - 1", "A - 2", "A - 3"))

    assert ok.status_code == 200
    assert too_many.status_code == 422
    assert "Máximo 2" in too_many.json()["detail"]


# --- Búsqueda -----------------------------------------------------------------

def test_search_sin_credenciales_usa_cliente_anonimo(api_env):
    response = api_env.client.get("/api/search", params={"q": "Oasis - Wonderwall"})

    assert response.status_code == 200
    assert response.json()["query"] == "Oasis - Wonderwall"
    assert response.json()["track"]["video_id"] == "vid-wonderwall"
    assert api_env.music.factory_calls == [None]


def test_search_con_credenciales_las_usa_y_sin_resultado_devuelve_null(api_env):
    connect(api_env)

    response = api_env.client.get("/api/search", params={"q": "Nadie - Nada"})

    assert response.status_code == 200
    assert response.json()["track"] is None
    assert api_env.music.factory_calls == [STORED_HEADERS]


def test_search_exige_q(api_env):
    assert api_env.client.get("/api/search").status_code == 422
    assert api_env.client.get("/api/search", params={"q": ""}).status_code == 422


# --- Playlists y jobs -----------------------------------------------------------

def test_crear_playlist_sin_credenciales_da_409(api_env):
    response = api_env.client.post("/api/playlists", json={"source": songs_source("Oasis - Wonderwall")})

    assert response.status_code == 409
    assert "YouTube Music" in response.json()["detail"]
    assert api_env.client.get("/api/jobs").json() == []
    assert api_env.music.created == []


def test_dry_run_sin_credenciales_termina_sin_escribir(api_env):
    body = {"source": songs_source("Oasis - Wonderwall", "Oasis - Desconocida"), "dry_run": True}

    response = api_env.client.post("/api/playlists", json=body)

    assert response.status_code == 202
    job = wait_for_job(api_env.client, response.json()["id"])
    assert job["status"] == "completed"
    assert job["dry_run"] is True
    assert job["playlist_id"] is None
    assert job["playlist_url"] is None
    assert job["summary"] == {
        "total": 2, "processed": 2, "found": 1, "added": 0, "duplicates": 0, "not_found": 1, "errors": 0,
    }
    assert job["items"][0]["track"]["video_id"] == "vid-wonderwall"
    assert api_env.music.created == []
    assert api_env.music.added == []
    assert api_env.music.factory_calls == [None]  # las búsquedas van sin sesión


def test_dry_run_con_credenciales_busca_con_ellas_y_no_escribe(api_env):
    connect(api_env)

    response = api_env.client.post(
        "/api/playlists?wait=true", json={"source": songs_source("Oasis - Wonderwall"), "dry_run": True}
    )

    assert response.status_code == 200
    assert response.json()["summary"]["found"] == 1
    assert api_env.music.factory_calls == [STORED_HEADERS]
    assert api_env.music.created == [] and api_env.music.added == []


def test_crear_playlist_con_wait_devuelve_el_resumen_final(api_env):
    connect(api_env)
    source = songs_source(
        "Oasis - Wonderwall",
        "Oasis - Live Forever",
        "Oasis - Wonderwall",  # repetida en la lista: duplicado
        "Oasis - Desconocida",  # no existe en YouTube Music
    )

    response = api_env.client.post(
        "/api/playlists?wait=true", json={"source": source, "privacy": "PRIVATE", "description": "mi descripción"}
    )

    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "completed"
    assert job["error"] is None
    assert job["owner_id"] == "local"
    assert job["summary"] == {
        "total": 4, "processed": 4, "found": 2, "added": 2, "duplicates": 1, "not_found": 1, "errors": 0,
    }
    assert [i["status"] for i in job["items"]] == ["found", "found", "duplicate", "not_found"]
    assert job["name"] == "Oasis - Concert Setlist"  # sugerido desde la fuente
    assert job["artist"] == "Oasis"
    assert job["playlist_id"] == "PLnueva"
    assert job["playlist_url"] == "https://music.youtube.com/playlist?list=PLnueva"
    assert job["started_at"] and job["finished_at"]
    assert api_env.music.created == [("Oasis - Concert Setlist", "mi descripción", Privacy.PRIVATE)]
    assert api_env.music.added == [("PLnueva", ["vid-wonderwall", "vid-liveforever"])]


def test_crear_playlist_usa_el_nombre_indicado(api_env):
    connect(api_env)

    response = api_env.client.post(
        "/api/playlists?wait=true", json={"source": songs_source("Oasis - Wonderwall"), "name": "Britpop 🎸"}
    )

    assert response.json()["name"] == "Britpop 🎸"
    assert api_env.music.created[0][0] == "Britpop 🎸"
    assert api_env.music.created[0][2] == Privacy.PUBLIC  # privacidad por defecto


def test_crear_playlist_sin_wait_devuelve_202_y_el_job_avanza(api_env):
    connect(api_env)

    response = api_env.client.post("/api/playlists", json={"source": songs_source("Oasis - Wonderwall")})

    assert response.status_code == 202
    job_id = response.json()["id"]
    assert response.json()["summary"]["total"] == 1
    assert wait_for_job(api_env.client, job_id)["summary"]["added"] == 1


def test_playlist_existente_por_url_agrega_ahi_y_salta_los_duplicados(api_build):
    music = FakeMusic(existing={"PLxyz": {"vid-wonderwall"}})
    env = api_build(music)
    connect(env)
    body = {
        "source": songs_source("Oasis - Wonderwall", "Oasis - Live Forever"),
        "playlist_id": "https://music.youtube.com/playlist?list=PLxyz&si=1",
    }

    response = env.client.post("/api/playlists?wait=true", json=body)

    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "completed"
    assert job["playlist_id"] == "PLxyz"
    assert job["playlist_url"] == "https://music.youtube.com/playlist?list=PLxyz"
    assert [i["status"] for i in job["items"]] == ["duplicate", "found"]
    assert job["summary"]["duplicates"] == 1 and job["summary"]["added"] == 1
    assert music.created == []  # no se crea una playlist nueva
    assert music.added == [("PLxyz", ["vid-liveforever"])]


def test_playlist_existente_por_id_directo(api_build):
    music = FakeMusic(existing={"PLabc": set()})
    env = api_build(music)
    connect(env)

    response = env.client.post(
        "/api/playlists?wait=true", json={"source": songs_source("Oasis - Supersonic"), "playlist_id": "PLabc"}
    )

    assert response.json()["playlist_id"] == "PLabc"
    assert music.added == [("PLabc", ["vid-supersonic"])]


def test_fallo_al_agregar_marca_los_items_en_error_pero_el_job_termina(api_env):
    connect(api_env)
    api_env.music.fail_add = "cuota agotada"
    source = songs_source("Oasis - Wonderwall", "Oasis - Live Forever", "Oasis - Desconocida")

    response = api_env.client.post("/api/playlists?wait=true", json={"source": source})

    job = response.json()
    assert response.status_code == 200
    assert job["status"] == "completed"
    assert job["error"] is None
    assert [i["status"] for i in job["items"]] == ["error", "error", "not_found"]
    assert "cuota agotada" in job["items"][0]["error"]
    assert job["summary"]["errors"] == 2
    assert job["summary"]["added"] == 0
    assert job["summary"]["not_found"] == 1
    assert job["playlist_id"] == "PLnueva"  # la playlist sí se alcanzó a crear


def test_fallo_al_crear_la_playlist_deja_el_job_en_failed(api_env):
    connect(api_env)
    api_env.music.fail_create = "YouTube Music no respondió"

    response = api_env.client.post("/api/playlists?wait=true", json={"source": songs_source("Oasis - Wonderwall")})

    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "failed"
    assert "YouTube Music no respondió" in job["error"]
    assert job["finished_at"]
    assert job["playlist_id"] is None
    assert job["summary"]["processed"] == 0
    assert api_env.music.searches == []  # ni siquiera empezó a buscar


def test_fallo_al_crear_el_cliente_deja_el_job_en_failed(api_build):
    env = api_build()
    connect(env)

    def broken_factory(headers):
        raise RuntimeError("headers corruptos")

    env.app.state.client_factory = broken_factory

    job = env.client.post("/api/playlists?wait=true", json={"source": songs_source("Oasis - Wonderwall")}).json()

    assert job["status"] == "failed"
    assert "No se pudo conectar con YouTube Music" in job["error"]
    assert "headers corruptos" in job["error"]


def test_mas_canciones_que_el_maximo_da_422(api_build):
    env = api_build(max_songs_per_job=2)
    connect(env)

    response = env.client.post(
        "/api/playlists?wait=true", json={"source": songs_source("A - 1", "A - 2", "A - 3")}
    )

    assert response.status_code == 422
    assert "Máximo 2" in response.json()["detail"]
    assert env.client.get("/api/jobs").json() == []
    assert env.music.created == []


@pytest.mark.parametrize(
    "extra",
    [{"privacy": "SECRETA"}, {"name": "x" * 151}, {"source": {"type": "songs", "songs": []}}],
)
def test_peticion_invalida_da_422(api_env, extra):
    connect(api_env)
    body = {"source": songs_source("Oasis - Wonderwall"), **extra}
    assert api_env.client.post("/api/playlists", json=body).status_code == 422


def test_playlist_desde_setlistfm(api_env, api_setlistfm):
    response = api_env.client.post(
        "/api/playlists?wait=true", json={"source": {"type": "setlistfm", "url": SETLISTFM_URL}, "dry_run": True}
    )

    job = response.json()
    assert response.status_code == 200
    assert job["artist"] == "The Hives"
    assert job["event_info"] == "Teatro Caupolicán - Mar 3, 2025"
    assert [i["query"] for i in job["items"]] == [
        "The Hives - Hate to Say I Told You So",
        "The Hives - Main Offender",
    ]


def test_listar_jobs_no_incluye_items_y_ordena_del_mas_reciente(api_env):
    connect(api_env)
    first = api_env.client.post("/api/playlists?wait=true", json={"source": songs_source("Oasis - Wonderwall")}).json()
    second = api_env.client.post("/api/playlists?wait=true", json={"source": songs_source("Oasis - Supersonic")}).json()

    listed = api_env.client.get("/api/jobs")

    assert listed.status_code == 200
    jobs = listed.json()
    assert [j["id"] for j in jobs] == [second["id"], first["id"]]
    assert all("items" not in j for j in jobs)
    assert jobs[0]["summary"]["added"] == 1
    # El detalle sí trae los items
    detail = api_env.client.get(f"/api/jobs/{first['id']}").json()
    assert len(detail["items"]) == 1
    assert detail["items"][0]["track"]["title"] == "Wonderwall"


def test_job_inexistente_da_404(api_env):
    response = api_env.client.get("/api/jobs/no-existe")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job no encontrado"


def test_job_de_otro_dueno_da_404(api_env):
    jobs = api_env.app.state.jobs
    foreign = jobs.new_job(owner_id="otro-usuario", dry_run=True)
    jobs.submit(foreign, lambda: api_env.music).result(timeout=5)

    assert api_env.client.get(f"/api/jobs/{foreign.id}").status_code == 404
    assert api_env.client.get("/api/jobs").json() == []


# --- Importación de headers_auth.json de la CLI -----------------------------------

@pytest.fixture
def api_legacy_file(tmp_path):
    path = tmp_path / "headers_auth.json"
    path.write_text(json.dumps({"authorization": "SAPISIDHASH 1_cli", "cookie": "SAPISID=desde-la-cli"}))
    return path


def test_importa_headers_de_la_cli_al_arrancar(api_build, api_legacy_file):
    env = api_build(legacy_headers_file=api_legacy_file)

    assert env.app.state.credential_store.get("local") == {
        "authorization": "SAPISIDHASH 1_cli",
        "cookie": "SAPISID=desde-la-cli",
    }
    assert env.client.get("/api/me").json()["ytmusic"]["connected"] is True


def test_no_pisa_credenciales_ya_guardadas(api_build, api_legacy_file, tmp_path):
    store = FileCredentialStore(tmp_path)
    store.set("local", STORED_HEADERS)

    env = api_build(store=store, legacy_headers_file=api_legacy_file)

    assert env.app.state.credential_store.get("local") == STORED_HEADERS


def test_sin_archivo_de_la_cli_no_hay_credenciales(api_build):
    env = api_build()
    assert env.app.state.credential_store.get("local") is None
    assert env.client.get("/api/me").json()["ytmusic"]["connected"] is False


def test_no_importa_headers_de_la_cli_en_modo_supabase(api_build, api_legacy_file):
    env = api_build(
        legacy_headers_file=api_legacy_file,
        auth_mode="supabase",
        supabase_url=SUPABASE_URL,
        supabase_jwt_secret=JWT_SECRET,
    )
    assert env.app.state.credential_store.get("local") is None


# --- Autenticación con Supabase (HS256) -----------------------------------------------

def make_token(sub: str = "user-a", secret: str = JWT_SECRET, expires_in: int = 3600, **overrides) -> str:
    claims: dict[str, Any] = {
        "sub": sub,
        "email": f"{sub}@example.com",
        "aud": "authenticated",
        "iss": ISSUER,
        "exp": int(time.time()) + expires_in,
        "user_metadata": {"full_name": "Ana Pérez", "avatar_url": "https://img.example/ana.png"},
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, secret, algorithm="HS256")


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api_sb(api_build) -> Env:
    return api_build(auth_mode="supabase", supabase_url=SUPABASE_URL, supabase_jwt_secret=JWT_SECRET)


def test_health_es_publico_en_modo_supabase(api_sb):
    response = api_sb.client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["auth_mode"] == "supabase"


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/api/me"),
        ("get", "/api/ytmusic/credentials"),
        ("put", "/api/ytmusic/credentials"),
        ("delete", "/api/ytmusic/credentials"),
        ("post", "/api/setlists/parse"),
        ("get", "/api/search"),
        ("post", "/api/playlists"),
        ("get", "/api/jobs"),
        ("get", "/api/jobs/abc"),
    ],
)
def test_sin_token_da_401(api_sb, method, path):
    assert getattr(api_sb.client, method)(path).status_code == 401


def test_sin_token_el_mensaje_es_claro(api_sb):
    response = api_sb.client.get("/api/me")
    assert response.status_code == 401
    assert "Falta el token" in response.json()["detail"]


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "Bearer basura"},
        {"Authorization": "Bearer "},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "token-sin-esquema"},
    ],
)
def test_token_malformado_da_401(api_sb, headers):
    assert api_sb.client.get("/api/me", headers=headers).status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(make_token(expires_in=-60), id="vencido"),
        pytest.param(make_token(secret="otro-secreto-hs256-distinto-con-largo-suficiente"), id="firma-mala"),
        pytest.param(make_token(aud="otra-audiencia"), id="audiencia-mala"),
        pytest.param(make_token(iss="https://otro.supabase.co/auth/v1"), id="emisor-malo"),
        pytest.param(make_token(sub=None), id="sin-sub"),
        pytest.param(make_token(exp=None), id="sin-exp"),
    ],
)
def test_token_invalido_da_401(api_sb, token):
    response = api_sb.client.get("/api/me", headers=bearer(token))
    assert response.status_code == 401
    assert response.json()["detail"].startswith("Token inválido")


def test_token_con_algoritmo_none_da_401(api_sb):
    token = jwt.encode({"sub": "x", "aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 60}, None, "none")
    assert api_sb.client.get("/api/me", headers=bearer(token)).status_code == 401


def test_token_valido_identifica_al_usuario(api_sb):
    response = api_sb.client.get("/api/me", headers=bearer(make_token(sub="3f2a-uuid")))

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "id": "3f2a-uuid",
        "email": "3f2a-uuid@example.com",
        "name": "Ana Pérez",
        "avatar_url": "https://img.example/ana.png",
    }
    assert body["auth_mode"] == "supabase"
    assert body["ytmusic"]["connected"] is False


def test_perfil_alternativo_de_google(api_sb):
    token = make_token(user_metadata={"name": "Ana G", "picture": "https://img.example/g.png"})

    user = api_sb.client.get("/api/me", headers=bearer(token)).json()["user"]

    assert user["name"] == "Ana G"
    assert user["avatar_url"] == "https://img.example/g.png"


def test_token_sin_metadata_ni_email(api_sb):
    token = make_token(user_metadata=None, email=None)

    user = api_sb.client.get("/api/me", headers=bearer(token)).json()["user"]

    assert user == {"id": "user-a", "email": None, "name": None, "avatar_url": None}


def test_audiencia_configurable(api_build):
    env = api_build(
        auth_mode="supabase",
        supabase_url=SUPABASE_URL,
        supabase_jwt_secret=JWT_SECRET,
        supabase_jwt_audience="mi-audiencia",
    )
    assert env.client.get("/api/me", headers=bearer(make_token())).status_code == 401
    assert env.client.get("/api/me", headers=bearer(make_token(aud="mi-audiencia"))).status_code == 200


def test_los_jobs_de_un_usuario_no_los_ve_otro(api_sb):
    ana, beto = bearer(make_token("ana")), bearer(make_token("beto"))
    created = api_sb.client.post(
        "/api/playlists?wait=true",
        json={"source": songs_source("Oasis - Wonderwall"), "dry_run": True},
        headers=ana,
    )
    job_id = created.json()["id"]

    assert created.json()["owner_id"] == "ana"
    assert [j["id"] for j in api_sb.client.get("/api/jobs", headers=ana).json()] == [job_id]
    assert api_sb.client.get(f"/api/jobs/{job_id}", headers=ana).status_code == 200
    assert api_sb.client.get("/api/jobs", headers=beto).json() == []
    assert api_sb.client.get(f"/api/jobs/{job_id}", headers=beto).status_code == 404


def test_las_credenciales_de_un_usuario_no_las_ve_otro(api_sb):
    ana, beto = bearer(make_token("ana")), bearer(make_token("beto"))

    assert api_sb.client.put("/api/ytmusic/credentials", json={"raw": CURL}, headers=ana).status_code == 200

    assert api_sb.client.get("/api/me", headers=ana).json()["ytmusic"]["connected"] is True
    assert api_sb.client.get("/api/me", headers=beto).json()["ytmusic"]["connected"] is False
    sin_credenciales = api_sb.client.post(
        "/api/playlists", json={"source": songs_source("Oasis - Wonderwall")}, headers=beto
    )
    assert sin_credenciales.status_code == 409
    # Y borrar las de Beto no toca las de Ana
    assert api_sb.client.delete("/api/ytmusic/credentials", headers=beto).status_code == 204
    assert api_sb.client.get("/api/me", headers=ana).json()["ytmusic"]["connected"] is True


# --- Autenticación con Supabase (JWKS, ES256) ----------------------------------------------

class FakeJWKSClient:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token: str):
        return SimpleNamespace(key=self.public_key)


@pytest.fixture
def api_jwks(api_build, monkeypatch):
    """Modo Supabase sin JWT secret: la firma se valida con la llave pública (JWKS simulado)."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(auth, "_jwks_client", lambda url: FakeJWKSClient(private_key.public_key()))
    env = api_build(auth_mode="supabase", supabase_url=SUPABASE_URL)
    return env, private_key


def es256_token(private_key, **overrides) -> str:
    claims = {"sub": "user-es", "aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 3600}
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="ES256")


def test_jwks_token_valido(api_jwks):
    env, private_key = api_jwks
    response = env.client.get("/api/me", headers=bearer(es256_token(private_key)))
    assert response.status_code == 200
    assert response.json()["user"]["id"] == "user-es"


def test_jwks_firma_de_otra_llave_da_401(api_jwks):
    env, _ = api_jwks
    otra = ec.generate_private_key(ec.SECP256R1())
    assert env.client.get("/api/me", headers=bearer(es256_token(otra))).status_code == 401


def test_jwks_token_vencido_da_401(api_jwks):
    env, private_key = api_jwks
    token = es256_token(private_key, exp=int(time.time()) - 60)
    assert env.client.get("/api/me", headers=bearer(token)).status_code == 401


def test_jwks_rechaza_tokens_hs256(api_jwks):
    """Sin secret configurado solo se aceptan algoritmos asimétricos."""
    env, _ = api_jwks
    assert env.client.get("/api/me", headers=bearer(make_token())).status_code == 401


# --- Selección del almacén de credenciales ----------------------------------------------

SB_SETTINGS = {
    "credential_store": "supabase",
    "supabase_url": SUPABASE_URL,
    "supabase_service_key": "sb_secret_abc",
    "credentials_encryption_key": Fernet.generate_key().decode(),
}


def test_por_defecto_el_almacen_es_un_archivo(tmp_path):
    app = create_app(make_settings(tmp_path))
    assert isinstance(app.state.credential_store, FileCredentialStore)


@pytest.mark.parametrize(
    "missing, env_name",
    [
        ("supabase_url", "SUPABASE_URL"),
        ("supabase_service_key", "SUPABASE_SERVICE_KEY"),
        ("credentials_encryption_key", "CREDENTIALS_ENCRYPTION_KEY"),
    ],
)
def test_almacen_supabase_con_variable_faltante_lanza_error(tmp_path, missing, env_name):
    settings = make_settings(tmp_path, **{**SB_SETTINGS, missing: None})

    with pytest.raises(RuntimeError, match=env_name):
        create_app(settings)


def test_almacen_supabase_sin_ninguna_variable_las_lista_todas(tmp_path):
    settings = make_settings(tmp_path, credential_store="supabase")

    with pytest.raises(RuntimeError) as exc_info:
        create_app(settings)

    for name in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "CREDENTIALS_ENCRYPTION_KEY"):
        assert name in str(exc_info.value)


def test_almacen_supabase_con_variable_vacia_lanza_error(tmp_path):
    settings = make_settings(tmp_path, **{**SB_SETTINGS, "supabase_service_key": ""})
    with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_KEY"):
        create_app(settings)


def test_almacen_supabase_con_clave_de_cifrado_invalida_lanza_error(tmp_path):
    settings = make_settings(tmp_path, **{**SB_SETTINGS, "credentials_encryption_key": "no-es-fernet"})
    with pytest.raises(ValueError, match="CREDENTIALS_ENCRYPTION_KEY"):
        create_app(settings)


def test_almacen_supabase_completo(tmp_path):
    app = create_app(make_settings(tmp_path, **SB_SETTINGS))

    store = app.state.credential_store
    assert isinstance(store, SupabaseCredentialStore)
    assert store.endpoint == f"{SUPABASE_URL}/rest/v1/ytmusic_credentials"


def test_un_almacen_inyectado_tiene_prioridad_y_no_se_valida(tmp_path):
    injected = FileCredentialStore(tmp_path / "otro")
    settings = make_settings(tmp_path, credential_store="supabase")  # sin variables

    app = create_app(settings, credential_store=injected)

    assert app.state.credential_store is injected


def test_las_variables_de_entorno_configuran_el_almacen(tmp_path, monkeypatch):
    monkeypatch.setenv("CREDENTIAL_STORE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "sb_secret_abc")
    monkeypatch.setenv("CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())

    app = create_app(Settings(_env_file=None, data_dir=tmp_path, frontend_dist=tmp_path / "sin-frontend"))

    assert isinstance(app.state.credential_store, SupabaseCredentialStore)


def test_flujo_completo_con_el_almacen_supabase(api_build, monkeypatch):
    """Las credenciales viajan cifradas hasta "Supabase" y vuelven a descifrarse para usarlas."""
    rows: dict[str, dict] = {}

    def fake_postgrest(method, url, **kwargs):
        response = requests.Response()
        response.status_code = 200
        params = kwargs.get("params") or {}
        user_id = params.get("user_id", "").removeprefix("eq.")
        if method == "POST":
            rows[kwargs["json"]["user_id"]] = kwargs["json"]
            response.status_code, response._content = 201, b""
        elif method == "DELETE":
            rows.pop(user_id, None)
            response.status_code, response._content = 204, b""
        else:
            row = rows.get(user_id)
            response._content = json.dumps([{"data": row["data"]}] if row else []).encode()
        return response

    monkeypatch.setattr(supabase_store.requests, "request", fake_postgrest)
    env = api_build(**SB_SETTINGS)

    assert env.client.get("/api/me").json()["ytmusic"]["connected"] is False
    assert env.client.put("/api/ytmusic/credentials", json={"raw": CURL}).status_code == 200

    assert list(rows) == ["local"]
    assert "abc123" not in json.dumps(rows) and "deadbeef" not in json.dumps(rows)
    assert env.client.get("/api/me").json()["ytmusic"]["connected"] is True
    assert env.music.factory_calls[-1]["authorization"] == "SAPISIDHASH 1700000000_deadbeef"

    assert env.client.delete("/api/ytmusic/credentials").status_code == 204
    assert rows == {}


# --- Frontend compilado -----------------------------------------------------------------

@pytest.fixture
def api_frontend(api_build, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>")
    (dist / "assets" / "app.js").write_text("console.log('app')")
    (tmp_path / "secreto.txt").write_text("fuera de dist")
    return api_build(frontend_dist=dist)


def test_sirve_el_frontend_compilado(api_frontend):
    assert api_frontend.client.get("/").text == "<html>spa</html>"
    assert api_frontend.client.get("/assets/app.js").text == "console.log('app')"
    assert api_frontend.client.get("/historial/abc").text == "<html>spa</html>"  # rutas del cliente
    assert api_frontend.client.get("/api/health").json()["status"] == "ok"  # la API sigue primero


def test_el_frontend_no_sirve_archivos_fuera_de_dist(api_frontend):
    for path in ("/../secreto.txt", "/%2e%2e/secreto.txt", "/..%2fsecreto.txt"):
        assert "fuera de dist" not in api_frontend.client.get(path).text


def test_ruta_api_inexistente_da_404_json_aunque_haya_frontend(api_frontend):
    response = api_frontend.client.get("/api/no-existe")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
