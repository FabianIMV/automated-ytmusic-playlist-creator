"""Tests del núcleo: YTMusicClient sin red (se reemplaza `.yt` por un falso)."""

from __future__ import annotations

import pytest

from playlist_creator.core.music import YTMusicClient, _to_track, extract_playlist_id, playlist_url
from playlist_creator.models import Privacy


class FakeYT:
    """Imita YTMusic.search / add_playlist_items / create_playlist.

    `search_responses` se consume en orden: cada elemento es una lista de resultados
    o una excepción que se lanza en esa llamada.
    """

    def __init__(self, search_responses=(), add_result=None, create_result="PLNEW"):
        self.search_responses = list(search_responses)
        self.search_calls: list[tuple[str, dict]] = []
        self.add_result = add_result if add_result is not None else {"status": "STATUS_SUCCEEDED"}
        self.add_calls: list[tuple[str, list, dict]] = []
        self.create_result = create_result
        self.create_calls: list[tuple] = []
        self.playlist_tracks: list[dict] = []

    def search(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        item = self.search_responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def add_playlist_items(self, playlist_id, video_ids, **kwargs):
        self.add_calls.append((playlist_id, list(video_ids), kwargs))
        return self.add_result

    def create_playlist(self, name, description, **kwargs):
        self.create_calls.append((name, description, kwargs))
        return self.create_result

    def get_playlist(self, playlist_id, limit=None):
        return {"tracks": self.playlist_tracks}


def make_client(yt: FakeYT) -> YTMusicClient:
    """Crea el cliente sin ejecutar __init__ (que construiría un YTMusic real)."""
    client = YTMusicClient.__new__(YTMusicClient)
    client.yt = yt
    return client


def resultado(video_id, result_type="song", **extra):
    return {"videoId": video_id, "resultType": result_type, "title": f"t-{video_id}", **extra}


# --- extract_playlist_id / playlist_url ------------------------------------


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("PLabc123", "PLabc123"),
        ("  PLabc123  ", "PLabc123"),
        ("VLPL123", "VLPL123"),
        ("https://music.youtube.com/playlist?list=PLabc123", "PLabc123"),
        ("https://music.youtube.com/playlist?list=PLabc123&si=xyz", "PLabc123"),
        ("https://music.youtube.com/playlist?list=PLabc123&si=xyz#frag", "PLabc123"),
        ("https://music.youtube.com/watch?v=abc&list=PLq9&index=2", "PLq9"),
    ],
)
def test_extract_playlist_id_acepta_id_o_url(entrada, esperado):
    assert extract_playlist_id(entrada) == esperado


def test_playlist_url_construye_la_url_de_music():
    assert playlist_url("PL1") == "https://music.youtube.com/playlist?list=PL1"


# --- _to_track -------------------------------------------------------------


def test_to_track_resultado_completo():
    track = _to_track(
        {
            "videoId": "vid1",
            "title": "Wonderwall",
            "artists": [{"name": "Oasis", "id": "UC1"}, {"name": None}],
            "album": {"name": "(What's the Story) Morning Glory?"},
            "duration": "4:18",
            "thumbnails": [{"url": "https://img/small.jpg"}, {"url": "https://img/big.jpg"}],
            "resultType": "song",
        }
    )

    assert track.video_id == "vid1"
    assert track.title == "Wonderwall"
    assert track.artists == ["Oasis"]  # los nombres None se descartan
    assert track.album == "(What's the Story) Morning Glory?"
    assert track.duration == "4:18"
    assert track.thumbnail == "https://img/big.jpg"  # la última miniatura es la de mayor tamaño
    assert track.result_type == "song"


def test_to_track_sin_album_devuelve_album_none():
    track = _to_track({"videoId": "v", "title": "x", "album": None})

    assert track.album is None


def test_to_track_sin_thumbnails_devuelve_thumbnail_none():
    assert _to_track({"videoId": "v", "title": "x"}).thumbnail is None
    assert _to_track({"videoId": "v", "title": "x", "thumbnails": []}).thumbnail is None


def test_to_track_artists_vacios_o_ausentes_devuelve_lista_vacia():
    assert _to_track({"videoId": "v", "title": "x", "artists": []}).artists == []
    assert _to_track({"videoId": "v", "title": "x"}).artists == []


def test_to_track_sin_titulo_usa_unknown():
    assert _to_track({"videoId": "v"}).title == "Unknown"


# --- search_track: orden de estrategias ------------------------------------


def test_search_track_primera_estrategia_devuelve_primer_song_de_busqueda_general():
    yt = FakeYT(
        search_responses=[
            [resultado("vidVideo", "video"), resultado("vidSong1"), resultado("vidSong2")],
        ]
    )

    track = make_client(yt).search_track("Oasis - Wonderwall")

    assert track is not None
    assert track.video_id == "vidSong1"
    # Encontrada en la primera estrategia: no se hacen más búsquedas
    assert len(yt.search_calls) == 1
    assert yt.search_calls[0] == ("Oasis - Wonderwall", {"limit": 10})


def test_search_track_sin_song_en_general_usa_filtro_songs():
    yt = FakeYT(
        search_responses=[
            [resultado("vidVideo", "video")],
            [resultado("vidFiltro", "song")],
        ]
    )

    track = make_client(yt).search_track("q")

    assert track.video_id == "vidFiltro"
    assert len(yt.search_calls) == 2
    assert yt.search_calls[1] == ("q", {"filter": "songs", "limit": 5})


def test_search_track_filtro_songs_acepta_cualquier_resultado_con_video_id():
    # Así funciona la estrategia 2 (igual que la CLI original): basta con videoId
    yt = FakeYT(search_responses=[[], [resultado("vidX", "video")]])

    assert make_client(yt).search_track("q").video_id == "vidX"


def test_search_track_cae_a_filtro_videos_si_lo_anterior_no_da_nada():
    yt = FakeYT(
        search_responses=[
            [],
            [],
            [resultado("vidVideo", "video")],
        ]
    )

    track = make_client(yt).search_track("q")

    assert track.video_id == "vidVideo"
    assert len(yt.search_calls) == 3
    assert yt.search_calls[2] == ("q", {"filter": "videos", "limit": 5})


def test_search_track_devuelve_none_si_ninguna_estrategia_encuentra_nada():
    yt = FakeYT(search_responses=[[], [], []])

    assert make_client(yt).search_track("nada") is None
    assert len(yt.search_calls) == 3


def test_search_track_ignora_resultados_sin_video_id_en_la_busqueda_general():
    yt = FakeYT(search_responses=[[{"resultType": "song"}, resultado("ok")]])

    assert make_client(yt).search_track("q").video_id == "ok"


def test_search_track_excepcion_en_primera_estrategia_pasa_a_la_siguiente():
    yt = FakeYT(
        search_responses=[
            RuntimeError("fallo de red"),
            [resultado("tras-error")],
        ]
    )

    track = make_client(yt).search_track("q")

    assert track.video_id == "tras-error"
    assert len(yt.search_calls) == 2


def test_search_track_excepciones_en_dos_estrategias_pasan_a_la_tercera():
    yt = FakeYT(
        search_responses=[
            RuntimeError("uno"),
            ValueError("dos"),
            [resultado("tercera", "video")],
        ]
    )

    assert make_client(yt).search_track("q").video_id == "tercera"


def test_search_track_todas_las_estrategias_fallan_devuelve_none():
    yt = FakeYT(search_responses=[RuntimeError("a"), RuntimeError("b"), RuntimeError("c")])

    assert make_client(yt).search_track("q") is None


# --- add_items / create_playlist / get_playlist_video_ids -------------------


def test_add_items_con_status_succeeded_no_lanza_y_no_pide_duplicados():
    yt = FakeYT(add_result={"status": "STATUS_SUCCEEDED", "playlistEditResults": []})

    make_client(yt).add_items("PLX", ["v1", "v2"])

    assert yt.add_calls == [("PLX", ["v1", "v2"], {"duplicates": False})]


def test_add_items_con_status_fallido_lanza():
    yt = FakeYT(add_result={"status": "STATUS_FAILED"})

    with pytest.raises(RuntimeError, match="rechazó el lote"):
        make_client(yt).add_items("PLX", ["v1"])


def test_add_items_sin_status_lanza():
    yt = FakeYT(add_result={})

    with pytest.raises(RuntimeError):
        make_client(yt).add_items("PLX", ["v1"])


def test_add_items_acepta_resultado_no_dict_con_succeeded():
    yt = FakeYT(add_result="STATUS_SUCCEEDED")

    make_client(yt).add_items("PLX", ["v1"])  # no debe lanzar


def test_create_playlist_pasa_privacidad_y_devuelve_id():
    yt = FakeYT(create_result="PLNEW")

    result = make_client(yt).create_playlist("Mi lista", "desc", Privacy.UNLISTED)

    assert result == "PLNEW"
    assert yt.create_calls == [("Mi lista", "desc", {"privacy_status": "UNLISTED"})]


def test_create_playlist_sin_id_en_texto_lanza():
    yt = FakeYT(create_result={"error": "algo"})

    with pytest.raises(RuntimeError, match="ID de playlist"):
        make_client(yt).create_playlist("x", "", Privacy.PRIVATE)


def test_get_playlist_video_ids_ignora_tracks_sin_video_id():
    yt = FakeYT()
    yt.playlist_tracks = [{"videoId": "a"}, {"videoId": None}, {"title": "sin id"}, {"videoId": "b"}]

    assert make_client(yt).get_playlist_video_ids("PL1") == {"a", "b"}
