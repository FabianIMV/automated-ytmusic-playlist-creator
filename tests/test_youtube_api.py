"""Tests del modo simple (YouTube Data API con token de Google), sin red."""

from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

from playlist_creator.api.main import create_app
from playlist_creator.config import Settings
from playlist_creator.core import youtube_api
from playlist_creator.core.builder import not_found_queries, prepare_job, run_job
from playlist_creator.core.youtube_api import (
    PartialAddError,
    QuotaExceededError,
    YouTubeApiError,
    YouTubeDataApiClient,
    google_credentials,
    is_google_credentials,
)
from playlist_creator.models import ItemStatus, Job, JobStatus, Privacy, Setlist, Track


class FakeResponse:
    def __init__(self, status_code: int, data: dict | None = None):
        self.status_code = status_code
        self._data = data or {}
        self.content = b"x" if data is not None else b""
        self.text = str(data)

    def json(self):
        return self._data


def api_error(status: int, reason: str, message: str = "boom") -> FakeResponse:
    return FakeResponse(status, {"error": {"message": message, "errors": [{"reason": reason}]}})


@pytest.fixture(autouse=True)
def limpiar_cache():
    youtube_api._token_cache.clear()
    yield
    youtube_api._token_cache.clear()


@pytest.fixture
def http(monkeypatch):
    """Registra las llamadas y responde según una lista de respuestas para la Data API."""
    calls: list[tuple[str, str, dict]] = []
    responses: list[FakeResponse] = []
    token_response = {"value": FakeResponse(200, {"access_token": "at-1", "expires_in": 3600})}

    def fake_post(url, data=None, timeout=None):
        calls.append(("POST", url, {"data": data}))
        return token_response["value"]

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        calls.append((method, url, {"headers": headers, **kwargs}))
        return responses.pop(0)

    monkeypatch.setattr(youtube_api.requests, "post", fake_post)
    monkeypatch.setattr(youtube_api.requests, "request", fake_request)
    return calls, responses, token_response


def client() -> YouTubeDataApiClient:
    return YouTubeDataApiClient("rt-123", "cid", "secret")


def test_formato_de_credenciales():
    creds = google_credentials("rt")
    assert is_google_credentials(creds)
    assert not is_google_credentials({"cookie": "SAPISID=1", "authorization": "SAPISIDHASH x"})
    assert not is_google_credentials(None)


def test_create_playlist_usa_privacidad_en_minusculas_y_token(http):
    calls, responses, _ = http
    responses.append(FakeResponse(200, {"id": "PLnew"}))

    assert client().create_playlist("Mi lista", "desc", Privacy.UNLISTED) == "PLnew"

    token_call, api_call = calls
    assert token_call[2]["data"]["grant_type"] == "refresh_token"
    assert token_call[2]["data"]["refresh_token"] == "rt-123"
    assert api_call[1].endswith("/playlists")
    assert api_call[2]["headers"]["Authorization"] == "Bearer at-1"
    assert api_call[2]["json"]["status"]["privacyStatus"] == "unlisted"
    assert api_call[2]["json"]["snippet"]["title"] == "Mi lista"


def test_access_token_se_cachea_entre_instancias(http):
    calls, responses, _ = http
    responses.extend([FakeResponse(200, {"id": "A"}), FakeResponse(200, {"id": "B"})])

    client().create_playlist("a", "", Privacy.PRIVATE)
    client().create_playlist("b", "", Privacy.PRIVATE)

    assert [c[1] for c in calls].count(youtube_api.TOKEN_URL) == 1


def test_refresh_token_revocado_da_mensaje_para_reconectar(http):
    _, _, token = http
    token["value"] = FakeResponse(400, {"error": "invalid_grant", "error_description": "Token has been expired"})

    with pytest.raises(YouTubeApiError, match="Vuelve a conectar con Google"):
        client().account_info()


def test_get_playlist_video_ids_pagina(http):
    calls, responses, _ = http
    responses.extend(
        [
            FakeResponse(200, {"items": [{"contentDetails": {"videoId": "v1"}}], "nextPageToken": "p2"}),
            FakeResponse(200, {"items": [{"contentDetails": {"videoId": "v2"}}]}),
        ]
    )

    assert client().get_playlist_video_ids("PL1") == {"v1", "v2"}
    assert calls[-1][2]["params"]["pageToken"] == "p2"


def test_add_items_agrega_de_a_uno(http):
    calls, responses, _ = http
    responses.extend([FakeResponse(200, {}), FakeResponse(200, {})])

    client().add_items("PL1", ["v1", "v2"])

    inserts = [c for c in calls if c[1].endswith("/playlistItems")]
    assert [c[2]["json"]["snippet"]["resourceId"]["videoId"] for c in inserts] == ["v1", "v2"]


def test_add_items_error_puntual_sigue_y_reporta_fallidas(http):
    _, responses, _ = http
    responses.extend([api_error(404, "videoNotFound"), FakeResponse(200, {})])

    with pytest.raises(PartialAddError) as info:
        client().add_items("PL1", ["v1", "v2"])

    assert info.value.failed_ids == {"v1"}
    assert not info.value.fatal


def test_add_items_cuota_agotada_corta_y_marca_el_resto(http):
    calls, responses, _ = http
    responses.extend([FakeResponse(200, {}), api_error(403, "quotaExceeded")])

    with pytest.raises(PartialAddError) as info:
        client().add_items("PL1", ["v1", "v2", "v3"])

    assert info.value.fatal
    assert info.value.failed_ids == {"v2", "v3"}
    assert "cuota" in str(info.value)
    assert len([c for c in calls if c[1].endswith("/playlistItems")]) == 2  # no intentó v3


@pytest.mark.parametrize(
    ("status", "reason", "fragmento"),
    [
        (403, "quotaExceeded", "cuota"),
        (403, "youtubeSignupRequired", "canal de YouTube"),
        (403, "accessNotConfigured", "no está habilitada"),
        (403, "insufficientPermissions", "permiso de YouTube"),
        (500, "backendError", "YouTube respondió 500"),
    ],
)
def test_errores_de_la_api_traducidos(http, status, reason, fragmento):
    _, responses, _ = http
    responses.append(api_error(status, reason))

    with pytest.raises(YouTubeApiError, match=fragmento):
        client().create_playlist("a", "", Privacy.PRIVATE)


def test_cuota_es_fatal():
    assert QuotaExceededError.fatal and not YouTubeApiError.fatal


def test_account_info_sin_canal(http):
    _, responses, _ = http
    responses.append(FakeResponse(200, {"items": []}))

    with pytest.raises(YouTubeApiError, match="canal de YouTube"):
        client().account_info()


def test_account_info_mapea_canal(http):
    _, responses, _ = http
    responses.append(
        FakeResponse(
            200,
            {"items": [{"snippet": {"title": "Fabián", "customUrl": "@fabian", "thumbnails": {"default": {"url": "u"}}}}]},
        )
    )

    assert client().account_info() == {"accountName": "Fabián", "channelHandle": "@fabian", "accountPhotoUrl": "u"}


# --- Builder con fallas parciales / fatales ----------------------------------


class PartialClient:
    def __init__(self, exc: Exception):
        self.exc = exc

    def search_track(self, query):
        return Track(video_id=query, title=query)

    def create_playlist(self, name, description, privacy):
        return "PL1"

    def get_playlist_video_ids(self, playlist_id):
        return set()

    def add_items(self, playlist_id, video_ids):
        raise self.exc

    def account_info(self):
        return {}


def _job(songs):
    from datetime import datetime, timezone

    job = Job(id="j", owner_id="u", created_at=datetime.now(timezone.utc))
    prepare_job(job, Setlist(songs=songs, suggested_name="n", suggested_description="d"))
    return job


def test_builder_cuenta_agregadas_en_falla_parcial():
    job = run_job(_job(["a", "b", "c"]), PartialClient(PartialAddError("x", {"b"})), batch_delay=0)

    assert job.status == JobStatus.COMPLETED
    assert job.summary.added == 2
    assert [i.status for i in job.items] == [ItemStatus.FOUND, ItemStatus.ERROR, ItemStatus.FOUND]


def test_builder_corta_el_job_si_la_falla_es_fatal():
    exc = PartialAddError("Se agotó la cuota", {"b", "c"}, fatal=True)
    job = run_job(_job(["a", "b", "c", "d"]), PartialClient(exc), batch_size=3, batch_delay=0)

    assert job.status == JobStatus.FAILED
    assert "cuota" in job.error
    assert job.summary.added == 1
    assert job.items[3].status == ItemStatus.PENDING  # el segundo lote nunca empezó
    assert not_found_queries(job) == ["b", "c", "d"]


# --- Endpoint PUT /api/ytmusic/google ------------------------------------------


class FakeGoogleClient:
    def __init__(self, creds, ok=True):
        self.creds, self.ok = creds, ok

    def account_info(self):
        if not self.ok:
            raise YouTubeApiError("Google revocó o venció el permiso de YouTube. Vuelve a conectar con Google.")
        return {"accountName": "Fabián", "channelHandle": "@fabian", "accountPhotoUrl": None}


def _app(tmp_path: pathlib.Path, ok=True, google=True):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        legacy_headers_file=tmp_path / "no.json",
        google_client_id="cid" if google else None,
        google_client_secret="secret" if google else None,
    )
    return create_app(settings, client_factory=lambda creds: FakeGoogleClient(creds, ok))


def test_health_informa_modo_simple(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        assert c.get("/api/health").json()["google_connect"] is True
    with TestClient(_app(tmp_path, google=False)) as c:
        assert c.get("/api/health").json()["google_connect"] is False


def test_conectar_google_guarda_y_reporta_modo(tmp_path):
    with TestClient(_app(tmp_path)) as c:
        r = c.put("/api/ytmusic/google", json={"refresh_token": "1//refresh-token"})
        assert r.status_code == 200
        assert r.json()["mode"] == "google"
        assert r.json()["account"]["name"] == "Fabián"
        me = c.get("/api/me").json()["ytmusic"]
        assert me["connected"] and me["mode"] == "google"
        assert c.delete("/api/ytmusic/credentials").status_code == 204
        assert c.get("/api/me").json()["ytmusic"]["connected"] is False


def test_conectar_google_rechazado_no_guarda(tmp_path):
    with TestClient(_app(tmp_path, ok=False)) as c:
        r = c.put("/api/ytmusic/google", json={"refresh_token": "1//refresh-token"})
        assert r.status_code == 422
        assert "Vuelve a conectar" in r.json()["detail"]
        assert c.get("/api/me").json()["ytmusic"]["connected"] is False


def test_conectar_google_sin_configurar_da_503(tmp_path):
    with TestClient(_app(tmp_path, google=False)) as c:
        assert c.put("/api/ytmusic/google", json={"refresh_token": "1//refresh-token"}).status_code == 503


def test_factory_por_defecto_elige_cliente_segun_modo(tmp_path):
    from playlist_creator.api.main import _default_client_factory
    from playlist_creator.core.music import YTMusicClient

    settings = Settings(_env_file=None, google_client_id="cid", google_client_secret="secret")
    factory = _default_client_factory(settings)
    assert isinstance(factory(google_credentials("rt")), YouTubeDataApiClient)
    yt = factory({"cookie": "SAPISID=1; __Secure-3PAPISID=1", "authorization": "SAPISIDHASH 1_x"})
    assert isinstance(yt, YTMusicClient)

    sin_google = _default_client_factory(Settings(_env_file=None))
    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_ID"):
        sin_google(google_credentials("rt"))
