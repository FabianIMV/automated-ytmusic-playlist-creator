"""Acceso a YouTube Music detrás de una interfaz pequeña (fácil de mockear o reemplazar).

La búsqueda funciona sin autenticación; crear/modificar playlists requiere credenciales.
Una futura implementación con la YouTube Data API (token de Google vía Supabase)
solo necesita cumplir `MusicClient`.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from ytmusicapi import YTMusic

from playlist_creator.models import Privacy, Track


class MusicClient(Protocol):
    def search_track(self, query: str) -> Track | None: ...
    def create_playlist(self, name: str, description: str, privacy: Privacy) -> str: ...
    def get_playlist_video_ids(self, playlist_id: str) -> set[str]: ...
    def add_items(self, playlist_id: str, video_ids: list[str]) -> None: ...
    def account_info(self) -> dict[str, Any]: ...


def extract_playlist_id(url_or_id: str) -> str:
    """Acepta un ID ("PL...", "VL...") o una URL con ?list=."""
    match = re.search(r"[?&]list=([^&#]+)", url_or_id)
    return match.group(1) if match else url_or_id.strip()


def playlist_url(playlist_id: str) -> str:
    return f"https://music.youtube.com/playlist?list={playlist_id}"


def _to_track(result: dict[str, Any]) -> Track:
    thumbs = result.get("thumbnails") or []
    album = result.get("album")
    return Track(
        video_id=result["videoId"],
        title=result.get("title") or "Unknown",
        artists=[a.get("name") for a in (result.get("artists") or []) if a.get("name")],
        album=album.get("name") if isinstance(album, dict) else None,
        duration=result.get("duration"),
        thumbnail=thumbs[-1]["url"] if thumbs else None,
        result_type=result.get("resultType"),
    )


class YTMusicClient:
    """Implementación con ytmusicapi. `auth=None` => solo búsquedas."""

    def __init__(self, auth: dict[str, str] | None = None, language: str = "en"):
        self.yt = YTMusic(auth=auth, language=language) if auth else YTMusic(language=language)

    def search_track(self, query: str) -> Track | None:
        # Mismas estrategias que la CLI original, en orden:
        # 1) búsqueda general -> primer resultado tipo "song"
        # 2) filtro "songs"   3) filtro "videos"
        strategies: list[tuple[dict[str, Any], bool]] = [
            ({"limit": 10}, True),
            ({"filter": "songs", "limit": 5}, False),
            ({"filter": "videos", "limit": 5}, False),
        ]
        for kwargs, songs_only in strategies:
            try:
                results = self.yt.search(query, **kwargs)
            except Exception:
                continue
            for r in results:
                if r.get("videoId") and (not songs_only or r.get("resultType") == "song"):
                    return _to_track(r)
        return None

    def create_playlist(self, name: str, description: str, privacy: Privacy) -> str:
        result = self.yt.create_playlist(name, description, privacy_status=privacy.value)
        if not isinstance(result, str):
            raise RuntimeError(f"YouTube Music no devolvió un ID de playlist: {result}")
        return result

    def get_playlist_video_ids(self, playlist_id: str) -> set[str]:
        data = self.yt.get_playlist(playlist_id, limit=None)
        return {t["videoId"] for t in data.get("tracks", []) if t.get("videoId")}

    def add_items(self, playlist_id: str, video_ids: list[str]) -> None:
        result = self.yt.add_playlist_items(playlist_id, video_ids, duplicates=False)
        status = result.get("status") if isinstance(result, dict) else result
        if "SUCCEEDED" not in str(status):
            raise RuntimeError(f"YouTube Music rechazó el lote: {status or result}")

    def account_info(self) -> dict[str, Any]:
        return self.yt.get_account_info()
