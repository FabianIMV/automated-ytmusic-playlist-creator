"""Lógica principal: buscar canciones y crear/llenar la playlist, reportando progreso.

No sabe nada de HTTP ni de la consola: la CLI y la API le pasan un `on_update`
que se invoca cada vez que cambia el estado del job.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone

from playlist_creator.core.music import MusicClient, extract_playlist_id, playlist_url
from playlist_creator.models import ItemResult, ItemStatus, Job, JobStatus, Setlist

OnUpdate = Callable[[Job], None]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _recount(job: Job) -> None:
    s = job.summary
    s.total = len(job.items)
    counts = {status: 0 for status in ItemStatus}
    for item in job.items:
        counts[item.status] += 1
    s.processed = s.total - counts[ItemStatus.PENDING]
    s.found = counts[ItemStatus.FOUND]
    s.duplicates = counts[ItemStatus.DUPLICATE]
    s.not_found = counts[ItemStatus.NOT_FOUND]
    s.errors = counts[ItemStatus.ERROR]


def prepare_job(job: Job, setlist: Setlist) -> None:
    """Completa nombre/descripción por defecto e inicializa los items."""
    job.artist = setlist.artist
    job.event_info = setlist.event_info
    job.name = job.name or setlist.suggested_name
    job.description = job.description if job.description is not None else setlist.suggested_description
    job.items = [ItemResult(index=i, query=song) for i, song in enumerate(setlist.songs)]
    _recount(job)


def run_job(
    job: Job,
    client: MusicClient,
    on_update: OnUpdate = lambda job: None,
    batch_size: int = 50,
    batch_delay: float = 3.0,
) -> Job:
    """Ejecuta el job completo. Nunca lanza: los errores quedan en `job.error`."""
    job.status = JobStatus.RUNNING
    job.started_at = _now()
    on_update(job)

    try:
        used_ids: set[str] = set()
        if not job.dry_run:
            if job.playlist_id:
                job.playlist_id = extract_playlist_id(job.playlist_id)
                used_ids = client.get_playlist_video_ids(job.playlist_id)
            else:
                job.playlist_id = client.create_playlist(job.name or "Playlist", job.description or "", job.privacy)
            job.playlist_url = playlist_url(job.playlist_id)
            on_update(job)

        batches = [job.items[i : i + batch_size] for i in range(0, len(job.items), batch_size)]
        for batch_num, batch in enumerate(batches, 1):
            to_add: list[ItemResult] = []
            for item in batch:
                try:
                    track = client.search_track(item.query)
                except Exception as exc:  # noqa: BLE001 - se reporta por canción
                    item.status, item.error = ItemStatus.ERROR, str(exc)
                else:
                    if track is None:
                        item.status = ItemStatus.NOT_FOUND
                    elif track.video_id in used_ids:
                        item.status, item.track = ItemStatus.DUPLICATE, track
                    else:
                        used_ids.add(track.video_id)
                        item.status, item.track = ItemStatus.FOUND, track
                        to_add.append(item)
                _recount(job)
                on_update(job)

            if to_add and not job.dry_run:
                try:
                    client.add_items(job.playlist_id, [i.track.video_id for i in to_add])
                    job.summary.added += len(to_add)
                except Exception as exc:  # noqa: BLE001
                    for item in to_add:
                        item.status, item.error = ItemStatus.ERROR, f"No se pudo agregar: {exc}"
                    _recount(job)
                on_update(job)

            if batch_num < len(batches) and not job.dry_run:
                time.sleep(batch_delay)

        job.status = JobStatus.COMPLETED
    except Exception as exc:  # noqa: BLE001
        job.status = JobStatus.FAILED
        job.error = str(exc)
    finally:
        job.finished_at = _now()
        on_update(job)
    return job


def not_found_queries(job: Job) -> list[str]:
    """Canciones a reintentar (no encontradas o con error)."""
    return [i.query for i in job.items if i.status in (ItemStatus.NOT_FOUND, ItemStatus.ERROR)]
