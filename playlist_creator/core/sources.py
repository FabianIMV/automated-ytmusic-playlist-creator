"""Convierte una fuente (texto, lista o setlist.fm) en un Setlist con metadatos sugeridos."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from playlist_creator.models import Setlist, SetlistFmSource, SongsSource, Source, TextSource

KEYWORDS_EN = "live concert setlist tour performance rock music playlist"
KEYWORDS_ES = "concierto en vivo setlist gira presentación música rock playlist"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class SourceError(ValueError):
    """La fuente no se pudo leer o no contiene canciones."""


def parse_lines(lines: list[str] | str) -> list[str]:
    """Limpia líneas: quita vacías y comentarios (#)."""
    if isinstance(lines, str):
        lines = lines.splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def guess_artist(songs: list[str]) -> str | None:
    """Asume formato "Artista - Canción" en la primera línea (como la CLI original)."""
    if songs and " - " in songs[0]:
        return songs[0].split(" - ")[0].strip() or None
    return None


def suggested_name(artist: str | None) -> str:
    return f"{artist} - Concert Setlist" if artist else "Concert Setlist"


def suggested_description(artist: str | None, event_info: str | None, song_count: int) -> str:
    parts = [
        f"🎸 {artist} Concert Setlist" if artist else "Concert Setlist",
        f"📍 {event_info}" if event_info else "",
        f"🎵 {song_count} songs",
        "",
        f"Keywords: {KEYWORDS_EN}",
        f"Palabras clave: {KEYWORDS_ES}",
    ]
    return "\n".join(p for p in parts if p)


def scrape_setlistfm(url: str, timeout: float = 15) -> tuple[str | None, str | None, list[str]]:
    """Lee artista, evento y canciones desde una página de setlist.fm."""
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SourceError(f"No se pudo descargar el setlist: {exc}") from exc

    soup = BeautifulSoup(response.content, "html.parser")

    artist = None
    meta_artist = soup.find("meta", property="og:title")
    if meta_artist and " Setlist" in meta_artist.get("content", ""):
        artist = meta_artist["content"].split(" Setlist")[0].strip()
    if not artist:
        for elem in (soup.find("a", class_="summary url"), soup.find("span", itemprop="name")):
            if elem and elem.get_text(strip=True):
                artist = elem.get_text(strip=True)
                break

    venue_elem = soup.find("a", class_="url fn")
    date_elem = soup.find("em", class_="link")
    venue = venue_elem.get_text(strip=True) if venue_elem else ""
    date = date_elem.get_text(strip=True) if date_elem else ""
    event_info = " - ".join(p for p in (venue, date) if p) or None

    prefix = f"{artist} - " if artist else ""
    songs = [
        f"{prefix}{name}"
        for elem in soup.find_all("a", class_="songLabel")
        if (name := elem.get_text(strip=True)) and not name.startswith("(")
    ]
    return artist, event_info, songs


def load_source(source: Source) -> Setlist:
    if isinstance(source, SetlistFmSource):
        artist, event_info, songs = scrape_setlistfm(source.url)
    elif isinstance(source, TextSource):
        songs = parse_lines(source.text)
        artist, event_info = guess_artist(songs), None
    elif isinstance(source, SongsSource):
        songs = parse_lines(source.songs)
        artist, event_info = guess_artist(songs), None
    else:  # pragma: no cover - el discriminador de pydantic lo impide
        raise SourceError(f"Fuente no soportada: {source!r}")

    if not songs:
        raise SourceError("La fuente no contiene canciones")

    return Setlist(
        artist=artist,
        event_info=event_info,
        songs=songs,
        suggested_name=suggested_name(artist),
        suggested_description=suggested_description(artist, event_info, len(songs)),
    )
