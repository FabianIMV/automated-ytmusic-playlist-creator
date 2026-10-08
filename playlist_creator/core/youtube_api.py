"""Modo simple: escribe en YouTube con la YouTube Data API v3 oficial y un token de Google.

El usuario autoriza el scope `youtube` al iniciar sesión con Google (vía Supabase); el
frontend entrega el refresh token y aquí se canjea por access tokens cuando hace falta.
Las búsquedas siguen usando YouTube Music (ytmusicapi sin sesión) porque `search.list`
de la Data API cuesta 100 unidades de cuota por llamada.

Cuota gratuita: 10.000 unidades/día por proyecto de Google Cloud. Crear playlist = 50,
agregar canción = 50, leer = 1  →  ~200 canciones por día.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import requests

from playlist_creator.core.music import YTMusicClient
from playlist_creator.models import Privacy, Track

GOOGLE_KIND = "google_oauth"  # marca en el CredentialStore para distinguirlo de los headers del navegador
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"

# Caché de access tokens por refresh token (duran ~1 h), compartida entre requests.
_token_cache: dict[str, tuple[str, float]] = {}
_token_lock = threading.Lock()


class YouTubeApiError(RuntimeError):
    """Error de la Data API con un mensaje listo para mostrar."""

    fatal = False  # si es True, no tiene sentido seguir con el resto del job


class QuotaExceededError(YouTubeApiError):
    fatal = True


class PartialAddError(RuntimeError):
    """Algunas canciones del lote no se pudieron agregar."""

    def __init__(self, message: str, failed_ids: set[str], fatal: bool = False):
        super().__init__(message)
        self.failed_ids = failed_ids
        self.fatal = fatal


def google_credentials(refresh_token: str) -> dict[str, str]:
    """Formato en que se guarda la conexión de Google en el CredentialStore."""
    return {"_kind": GOOGLE_KIND, "refresh_token": refresh_token}


def is_google_credentials(creds: dict[str, str] | None) -> bool:
    return bool(creds) and creds.get("_kind") == GOOGLE_KIND


def _error_message(response: requests.Response) -> tuple[str, str]:
    try:
        error = response.json().get("error", {})
    except ValueError:
        return "", response.text[:200]
    if isinstance(error, str):  # endpoint de tokens: {"error": "invalid_grant", ...}
        return error, response.json().get("error_description", error)
    reasons = [e.get("reason", "") for e in error.get("errors", [])]
    return (reasons[0] if reasons else ""), error.get("message", "")


class YouTubeDataApiClient:
    def __init__(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        language: str = "en",
        timeout: float = 15.0,
    ):
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self._language = language
        self._search: YTMusicClient | None = None

    # --- Token ---------------------------------------------------------------

    def _access_token(self) -> str:
        with _token_lock:
            cached = _token_cache.get(self.refresh_token)
            if cached and cached[1] > time.time() + 60:
                return cached[0]
        try:
            response = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise YouTubeApiError(f"No se pudo contactar a Google: {exc}") from exc
        if response.status_code != 200:
            reason, message = _error_message(response)
            if reason == "invalid_grant":
                raise YouTubeApiError(
                    "Google revocó o venció el permiso de YouTube. Vuelve a conectar con Google."
                )
            raise YouTubeApiError(f"Google rechazó el token ({response.status_code}): {message or reason}")
        data = response.json()
        token = data["access_token"]
        with _token_lock:
            _token_cache[self.refresh_token] = (token, time.time() + int(data.get("expires_in", 3600)))
        return token

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        try:
            response = requests.request(method, f"{API}/{path}", headers=headers, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise YouTubeApiError(f"No se pudo contactar a YouTube: {exc}") from exc
        if response.status_code < 400:
            return response.json() if response.content else {}

        reason, message = _error_message(response)
        if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
            raise QuotaExceededError(
                "Se agotó la cuota diaria de la YouTube Data API (~200 canciones por día). "
                "Reintenta mañana o usa el modo avanzado (cURL)."
            )
        if reason == "youtubeSignupRequired":
            raise YouTubeApiError("Tu cuenta de Google no tiene canal de YouTube: créalo en youtube.com y reintenta.")
        if reason == "accessNotConfigured":
            raise YouTubeApiError("La YouTube Data API v3 no está habilitada en el proyecto de Google Cloud.")
        if reason in ("insufficientPermissions", "forbidden") or response.status_code == 401:
            raise YouTubeApiError("Falta el permiso de YouTube. Vuelve a conectar con Google y acéptalo.")
        raise YouTubeApiError(f"YouTube respondió {response.status_code}: {message or reason}")

    # --- MusicClient -----------------------------------------------------------

    def search_track(self, query: str) -> Track | None:
        if self._search is None:
            self._search = YTMusicClient(language=self._language)
        return self._search.search_track(query)

    def create_playlist(self, name: str, description: str, privacy: Privacy) -> str:
        data = self._request(
            "POST",
            "playlists",
            params={"part": "snippet,status"},
            json={
                "snippet": {"title": name, "description": description},
                "status": {"privacyStatus": privacy.value.lower()},
            },
        )
        return data["id"]

    def get_playlist_video_ids(self, playlist_id: str) -> set[str]:
        ids: set[str] = set()
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50}
        while True:
            data = self._request("GET", "playlistItems", params=params)
            ids.update(i["contentDetails"]["videoId"] for i in data.get("items", []))
            if not data.get("nextPageToken"):
                return ids
            params["pageToken"] = data["nextPageToken"]

    def add_items(self, playlist_id: str, video_ids: list[str]) -> None:
        # La Data API agrega de a una canción por llamada.
        failed: dict[str, str] = {}
        for n, video_id in enumerate(video_ids):
            body = {"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
            try:
                self._request("POST", "playlistItems", params={"part": "snippet"}, json=body)
            except YouTubeApiError as exc:
                if exc.fatal:  # p. ej. cuota agotada: no se agrega nada más
                    raise PartialAddError(str(exc), {video_id, *video_ids[n + 1 :]}, fatal=True) from exc
                failed[video_id] = str(exc)  # error puntual (video no disponible, etc.)
        if failed:
            raise PartialAddError(next(iter(failed.values())), set(failed))

    def account_info(self) -> dict[str, Any]:
        data = self._request("GET", "channels", params={"part": "snippet", "mine": "true"})
        items = data.get("items") or []
        if not items:
            raise YouTubeApiError("Tu cuenta de Google no tiene canal de YouTube: créalo en youtube.com y reintenta.")
        snippet = items[0]["snippet"]
        thumbs = snippet.get("thumbnails") or {}
        photo = (thumbs.get("default") or thumbs.get("medium") or {}).get("url")
        return {"accountName": snippet.get("title"), "channelHandle": snippet.get("customUrl"), "accountPhotoUrl": photo}
