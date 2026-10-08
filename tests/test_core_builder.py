"""Tests del núcleo: prepare_job / run_job / not_found_queries con un cliente falso (sin red)."""

from __future__ import annotations

from datetime import datetime, timezone


from playlist_creator.core.builder import not_found_queries, prepare_job, run_job
from playlist_creator.models import ItemStatus, Job, JobStatus, Privacy, Setlist, Track

SUGERIDA = "Descripción sugerida"
PLAYLIST_URL_EXISTENTE = "https://music.youtube.com/playlist?list=PLEXIST"


class FakeClient:
    """Cliente falso que cumple `MusicClient`.

    - `results`: query -> Track | None | Exception (lo que devuelve o lanza search_track).
    - `add_script`: lista consumida en cada llamada a add_items; un Exception se lanza,
      None significa éxito. Si se agota, todas las llamadas tienen éxito.
    """

    def __init__(self, results=None, existing=(), create_error=None, add_script=(), add_error=None):
        self.results = results or {}
        self.existing = set(existing)
        self.create_error = create_error
        self.add_script = list(add_script)
        self.add_error = add_error
        self.searched: list[str] = []
        self.created: list[tuple[str, str, Privacy]] = []
        self.added: list[tuple[str, list[str]]] = []  # solo llamadas exitosas
        self.add_attempts: list[tuple[str, list[str]]] = []
        self.existing_calls: list[str] = []

    def search_track(self, query):
        self.searched.append(query)
        value = self.results.get(query)
        if isinstance(value, Exception):
            raise value
        return value

    def create_playlist(self, name, description, privacy):
        if self.create_error is not None:
            raise self.create_error
        self.created.append((name, description, privacy))
        return "PLNEW"

    def get_playlist_video_ids(self, playlist_id):
        self.existing_calls.append(playlist_id)
        return set(self.existing)

    def add_items(self, playlist_id, video_ids):
        self.add_attempts.append((playlist_id, list(video_ids)))
        step = self.add_script.pop(0) if self.add_script else None
        error = step if step is not None else self.add_error
        if error is not None:
            raise error
        self.added.append((playlist_id, list(video_ids)))

    def account_info(self):
        return {}


def track(video_id, title="Tema", artist="Artista"):
    return Track(video_id=video_id, title=title, artists=[artist], result_type="song")


def setlist(songs, **kwargs):
    defaults = dict(
        artist="Oasis",
        event_info="Wembley - Jul 2025",
        suggested_name="Oasis - Concert Setlist",
        suggested_description=SUGERIDA,
    )
    defaults.update(kwargs)
    return Setlist(songs=songs, **defaults)


def new_job(**kwargs) -> Job:
    return Job(id="job1", owner_id="test", created_at=datetime.now(timezone.utc), **kwargs)


def run(job, client, **kwargs):
    kwargs.setdefault("batch_delay", 0)
    return run_job(job, client, **kwargs)


def prepared(songs, **job_kwargs) -> Job:
    job = new_job(**job_kwargs)
    prepare_job(job, setlist(songs))
    return job


# --- prepare_job -----------------------------------------------------------


def test_prepare_job_usa_nombre_y_descripcion_sugeridos_si_no_hay_nombre():
    job = new_job()
    prepare_job(job, setlist(["Oasis - Wonderwall", "Oasis - Hello"]))

    assert job.name == "Oasis - Concert Setlist"
    assert job.description == SUGERIDA
    assert job.artist == "Oasis"
    assert job.event_info == "Wembley - Jul 2025"
    assert [i.query for i in job.items] == ["Oasis - Wonderwall", "Oasis - Hello"]
    assert [i.index for i in job.items] == [0, 1]
    assert all(i.status == ItemStatus.PENDING for i in job.items)
    assert job.summary.total == 2
    assert job.summary.processed == 0


def test_prepare_job_respeta_nombre_del_usuario():
    job = new_job(name="Mi lista")
    prepare_job(job, setlist(["A - a"]))

    assert job.name == "Mi lista"


def test_prepare_job_respeta_descripcion_vacia():
    job = new_job(description="")
    prepare_job(job, setlist(["A - a"]))

    assert job.description == ""


def test_prepare_job_descripcion_none_usa_la_sugerida():
    job = new_job(description=None)
    prepare_job(job, setlist(["A - a"]))

    assert job.description == SUGERIDA


# --- run_job: creación, lotes y estados ------------------------------------


def test_run_job_crea_playlist_con_nombre_descripcion_y_privacidad():
    client = FakeClient(results={"A - a": track("v1")})
    job = prepared(["A - a"], name="Mi lista", description="desc", privacy=Privacy.PRIVATE)

    result = run(job, client)

    assert result is job
    assert client.created == [("Mi lista", "desc", Privacy.PRIVATE)]
    assert job.status == JobStatus.COMPLETED
    assert job.playlist_id == "PLNEW"
    assert job.playlist_url == "https://music.youtube.com/playlist?list=PLNEW"
    assert job.started_at is not None and job.finished_at is not None
    assert job.error is None


def test_run_job_agrupa_en_lotes_de_batch_size():
    songs = ["A - a", "A - b", "A - c", "A - d", "A - e"]
    client = FakeClient(results={s: track(f"v{i}") for i, s in enumerate(songs)})
    job = prepared(songs)

    run(job, client, batch_size=2)

    assert [len(ids) for _, ids in client.added] == [2, 2, 1]
    assert client.added[0] == ("PLNEW", ["v0", "v1"])
    assert job.summary.added == 5
    assert job.summary.found == 5


def test_run_job_deduplica_videos_repetidos_dentro_de_la_lista():
    client = FakeClient(
        results={
            "q1": track("v1"),
            "q2": track("v1"),  # mismo video que q1
            "q3": track("v2"),
        }
    )
    job = prepared(["q1", "q2", "q3"])

    run(job, client)

    assert [i.status for i in job.items] == [ItemStatus.FOUND, ItemStatus.DUPLICATE, ItemStatus.FOUND]
    assert client.added == [("PLNEW", ["v1", "v2"])]
    assert job.summary.duplicates == 1
    assert job.summary.added == 2


def test_run_job_misma_cancion_repetida_es_duplicada():
    client = FakeClient(results={"q": track("v1")})
    job = prepared(["q", "q"])

    run(job, client)

    assert [i.status for i in job.items] == [ItemStatus.FOUND, ItemStatus.DUPLICATE]
    assert client.added == [("PLNEW", ["v1"])]


def test_run_job_respeta_canciones_ya_existentes_con_playlist_id():
    client = FakeClient(
        results={"A - a": track("v1"), "A - b": track("v2")},
        existing={"v1"},
    )
    job = prepared(["A - a", "A - b"], playlist_id=PLAYLIST_URL_EXISTENTE)

    run(job, client)

    assert client.existing_calls == ["PLEXIST"]  # la URL se normaliza a ID
    assert client.created == []  # no crea playlist nueva
    assert job.playlist_id == "PLEXIST"
    assert job.items[0].status == ItemStatus.DUPLICATE
    assert job.items[1].status == ItemStatus.FOUND
    assert client.added == [("PLEXIST", ["v2"])]


def test_run_job_dry_run_no_crea_ni_agrega_nada():
    client = FakeClient(results={"A - a": track("v1"), "A - b": None}, existing={"v9"})
    job = prepared(["A - a", "A - b"], dry_run=True)

    run(job, client)

    assert client.created == []
    assert client.added == []
    assert client.add_attempts == []
    assert client.existing_calls == []
    assert job.status == JobStatus.COMPLETED
    assert job.playlist_id is None
    assert job.summary.found == 1
    assert job.summary.not_found == 1
    assert job.summary.added == 0


def test_run_job_dry_run_con_playlist_id_no_lee_la_playlist():
    client = FakeClient(results={"A - a": track("v1")}, existing={"v1"})
    job = prepared(["A - a"], dry_run=True, playlist_id=PLAYLIST_URL_EXISTENTE)

    run(job, client)

    assert client.existing_calls == []
    assert job.items[0].status == ItemStatus.FOUND


def test_run_job_error_en_add_marca_items_como_error():
    client = FakeClient(results={"A - a": track("v1"), "A - b": track("v2")}, add_error=RuntimeError("rechazado"))
    job = prepared(["A - a", "A - b"])

    run(job, client)

    assert job.status == JobStatus.COMPLETED  # el job termina; el error queda por canción
    assert [i.status for i in job.items] == [ItemStatus.ERROR, ItemStatus.ERROR]
    assert all("rechazado" in i.error for i in job.items)
    assert job.summary.added == 0
    assert job.summary.errors == 2
    assert not_found_queries(job) == ["A - a", "A - b"]


def test_run_job_error_en_un_lote_no_impide_los_siguientes():
    client = FakeClient(
        results={"s1": track("v1"), "s2": track("v2"), "s3": track("v3")},
        add_script=[RuntimeError("lote 1 falla")],
    )
    job = prepared(["s1", "s2", "s3"])

    run(job, client, batch_size=2)

    assert [i.status for i in job.items] == [ItemStatus.ERROR, ItemStatus.ERROR, ItemStatus.FOUND]
    assert client.added == [("PLNEW", ["v3"])]
    assert job.summary.added == 1


def test_run_job_error_al_buscar_una_cancion_no_detiene_el_job():
    client = FakeClient(results={"s1": track("v1"), "s2": RuntimeError("timeout"), "s3": track("v3")})
    job = prepared(["s1", "s2", "s3"])

    run(job, client)

    assert job.status == JobStatus.COMPLETED
    assert job.items[1].status == ItemStatus.ERROR
    assert job.items[1].error == "timeout"
    assert job.items[2].status == ItemStatus.FOUND
    assert not_found_queries(job) == ["s2"]


def test_run_job_error_al_crear_playlist_marca_job_failed_sin_buscar():
    client = FakeClient(results={"A - a": track("v1")}, create_error=RuntimeError("cuota agotada"))
    job = prepared(["A - a"])

    result = run(job, client)  # no debe lanzar

    assert result.status == JobStatus.FAILED
    assert "cuota agotada" in result.error
    assert result.finished_at is not None
    assert client.searched == []
    assert client.added == []


def test_run_job_llama_on_update_durante_la_ejecucion():
    client = FakeClient(results={"A - a": track("v1"), "A - b": None})
    job = prepared(["A - a", "A - b"])
    estados = []

    run(job, client, on_update=lambda j: estados.append((j.status, j.summary.processed)))

    assert estados[0][0] == JobStatus.RUNNING  # primera notificación: al empezar
    assert estados[-1][0] == JobStatus.COMPLETED  # última: al terminar
    # Al menos una notificación por canción procesada
    assert len(estados) >= 2
    procesados = [p for _, p in estados]
    assert procesados == sorted(procesados)  # nunca retrocede


def test_run_job_on_update_por_defecto_no_falla():
    job = prepared(["A - a"])

    run(job, FakeClient(results={"A - a": track("v1")}))  # sin on_update

    assert job.status == JobStatus.COMPLETED


# --- not_found_queries -----------------------------------------------------


def test_not_found_queries_incluye_no_encontradas_y_errores_en_orden():
    client = FakeClient(
        results={
            "ok": track("v1"),
            "dup": track("v1"),
            "nf": None,
            "err": RuntimeError("boom"),
        }
    )
    job = prepared(["ok", "dup", "nf", "err"])

    run(job, client)

    assert [i.status for i in job.items] == [
        ItemStatus.FOUND,
        ItemStatus.DUPLICATE,
        ItemStatus.NOT_FOUND,
        ItemStatus.ERROR,
    ]
    assert not_found_queries(job) == ["nf", "err"]


def test_not_found_queries_sin_pendientes_devuelve_lista_vacia():
    job = prepared(["A - a"])

    assert not_found_queries(job) == []


# --- Caso que revela un bug en el núcleo -----------------------------------


def test_repeticion_tras_fallo_de_add_no_se_pierde():
    client = FakeClient(
        results={"A - a": track("v1"), "A - b": track("v1")},
        add_script=[RuntimeError("rechazado"), None],
    )
    job = prepared(["A - a", "A - b"])

    run(job, client, batch_size=1)

    # Lo esperado: la segunda canción se agrega en el segundo lote (v1 nunca llegó a la playlist)
    assert job.items[1].status == ItemStatus.FOUND
    assert client.added == [("PLNEW", ["v1"])]
