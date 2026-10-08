"""Tests del núcleo: conversión de fuentes a Setlist (sin red: requests.get va mockeado)."""

from __future__ import annotations

import pytest
import requests

from playlist_creator.core import sources
from playlist_creator.core.sources import (
    SourceError,
    guess_artist,
    load_source,
    parse_lines,
    scrape_setlistfm,
    suggested_description,
    suggested_name,
)
from playlist_creator.models import SetlistFmSource, SongsSource, TextSource

SETLIST_HTML = b"""<html><head>
<meta property="og:title" content="Oasis Setlist at Wembley Stadium">
</head><body>
<a class="url fn">Wembley Stadium</a>
<em class="link">Jul 2025</em>
<ol>
  <li><a class="songLabel">Hello</a></li>
  <li><a class="songLabel">(Intro)</a></li>
  <li><a class="songLabel">Wonderwall</a></li>
</ol>
</body></html>"""

SETLIST_URL = "https://www.setlist.fm/setlist/oasis/2025/wembley-stadium-london-abc123.html"


class FakeResponse:
    def __init__(self, content: bytes, ok: bool = True):
        self.content = content
        self._ok = ok

    def raise_for_status(self):
        if not self._ok:
            raise requests.HTTPError("404 Client Error: Not Found")


@pytest.fixture
def fake_get(monkeypatch):
    """Reemplaza requests.get y guarda las llamadas. Por defecto responde SETLIST_HTML."""
    calls = []
    state = {"response": FakeResponse(SETLIST_HTML), "error": None}

    def _get(url, **kwargs):
        calls.append((url, kwargs))
        if state["error"] is not None:
            raise state["error"]
        return state["response"]

    monkeypatch.setattr(sources.requests, "get", _get)
    _get.calls = calls
    _get.state = state
    return _get


# --- Utilidades de texto ---------------------------------------------------


def test_parse_lines_desde_texto_quita_vacias_y_comentarios():
    texto = "  Oasis - Wonderwall  \n\n# comentario\n   \nBlur - Song 2\n   # indentado\n"

    assert parse_lines(texto) == ["Oasis - Wonderwall", "Blur - Song 2"]


def test_parse_lines_desde_lista():
    assert parse_lines([" A - a ", "", "#x", "B - b"]) == ["A - a", "B - b"]


def test_guess_artist_toma_lo_que_va_antes_del_primer_guion():
    assert guess_artist(["Oasis - Wonderwall", "Blur - Song 2"]) == "Oasis"
    assert guess_artist(["Oasis - Wonderwall - Live"]) == "Oasis"


def test_guess_artist_sin_formato_o_sin_canciones_devuelve_none():
    assert guess_artist(["Wonderwall"]) is None
    assert guess_artist([]) is None


def test_suggested_name_con_y_sin_artista():
    assert suggested_name("Oasis") == "Oasis - Concert Setlist"
    assert suggested_name(None) == "Concert Setlist"


def test_suggested_description_incluye_artista_evento_conteo_y_keywords():
    desc = suggested_description("Oasis", "Wembley - Jul 2025", 3)

    assert desc.splitlines()[0] == "🎸 Oasis Concert Setlist"
    assert "📍 Wembley - Jul 2025" in desc
    assert "🎵 3 songs" in desc
    assert "Keywords:" in desc
    assert "Palabras clave:" in desc


def test_suggested_description_sin_artista_ni_evento():
    desc = suggested_description(None, None, 1)

    assert desc.splitlines()[0] == "Concert Setlist"
    assert "📍" not in desc
    assert "🎵 1 songs" in desc


# --- load_source -----------------------------------------------------------


def test_load_source_texto_devuelve_setlist_con_sugeridos():
    setlist = load_source(TextSource(text="Oasis - Wonderwall\nBlur - Song 2\n# nota\n"))

    assert setlist.songs == ["Oasis - Wonderwall", "Blur - Song 2"]
    assert setlist.artist == "Oasis"
    assert setlist.event_info is None
    assert setlist.suggested_name == "Oasis - Concert Setlist"
    assert "🎵 2 songs" in setlist.suggested_description


def test_load_source_lista_de_canciones():
    setlist = load_source(SongsSource(songs=["Oasis - Wonderwall", "   ", "# x", "Blur - Song 2"]))

    assert setlist.songs == ["Oasis - Wonderwall", "Blur - Song 2"]
    assert setlist.artist == "Oasis"


@pytest.mark.parametrize(
    "source",
    [
        TextSource(text="# solo comentarios\n   \n"),
        SongsSource(songs=["# nada", "  "]),
    ],
)
def test_load_source_sin_canciones_lanza_source_error(source):
    with pytest.raises(SourceError, match="no contiene canciones"):
        load_source(source)


# --- scrape_setlistfm (requests mockeado) ---------------------------------


def test_scrape_setlistfm_extrae_artista_evento_y_canciones(fake_get):
    artist, event_info, songs = scrape_setlistfm(SETLIST_URL)

    assert artist == "Oasis"
    assert event_info == "Wembley Stadium - Jul 2025"
    # "(Intro)" es una anotación y se omite
    assert songs == ["Oasis - Hello", "Oasis - Wonderwall"]


def test_scrape_setlistfm_envia_user_agent_y_timeout(fake_get):
    scrape_setlistfm(SETLIST_URL, timeout=7)

    url, kwargs = fake_get.calls[0]
    assert url == SETLIST_URL
    assert "Mozilla" in kwargs["headers"]["User-Agent"]
    assert kwargs["timeout"] == 7


def test_scrape_setlistfm_sin_og_title_usa_el_nombre_del_html(fake_get):
    fake_get.state["response"] = FakeResponse(b'<span itemprop="name">Blur</span><a class="songLabel">Song 2</a>')

    artist, event_info, songs = scrape_setlistfm(SETLIST_URL)

    assert artist == "Blur"
    assert event_info is None
    assert songs == ["Blur - Song 2"]


def test_scrape_setlistfm_sin_artista_deja_nombres_sin_prefijo(fake_get):
    fake_get.state["response"] = FakeResponse(b'<a class="songLabel">Hello</a>')

    artist, _, songs = scrape_setlistfm(SETLIST_URL)

    assert artist is None
    assert songs == ["Hello"]


def test_scrape_setlistfm_error_de_red_lanza_source_error(fake_get):
    fake_get.state["error"] = requests.ConnectionError("sin conexión")

    with pytest.raises(SourceError, match="No se pudo descargar"):
        scrape_setlistfm(SETLIST_URL)


def test_scrape_setlistfm_http_404_lanza_source_error(fake_get):
    fake_get.state["response"] = FakeResponse(b"", ok=False)

    with pytest.raises(SourceError, match="No se pudo descargar"):
        scrape_setlistfm(SETLIST_URL)


def test_load_source_setlistfm_usa_el_scraper(fake_get):
    setlist = load_source(SetlistFmSource(url=SETLIST_URL))

    assert setlist.artist == "Oasis"
    assert setlist.event_info == "Wembley Stadium - Jul 2025"
    assert setlist.songs == ["Oasis - Hello", "Oasis - Wonderwall"]
    assert setlist.suggested_name == "Oasis - Concert Setlist"


def test_load_source_setlistfm_con_red_caida_lanza_source_error(fake_get):
    fake_get.state["error"] = requests.Timeout("timeout")

    with pytest.raises(SourceError):
        load_source(SetlistFmSource(url=SETLIST_URL))
