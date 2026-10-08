"""Jobs en memoria ejecutados en un pool de threads.

Suficiente para uso personal / una instancia. Para varias instancias o
persistencia, reemplazar por una tabla (p. ej. en Supabase) con la misma interfaz.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone

from playlist_creator.core.builder import run_job
from playlist_creator.core.music import MusicClient
from playlist_creator.models import Job, JobStatus

MAX_JOBS_KEPT = 200


class JobManager:
    def __init__(self, workers: int = 2, batch_size: int = 50, batch_delay: float = 3.0):
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="playlist-job")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self.batch_size = batch_size
        self.batch_delay = batch_delay

    def new_job(self, owner_id: str, **fields) -> Job:
        return Job(id=uuid.uuid4().hex, owner_id=owner_id, created_at=datetime.now(timezone.utc), **fields)

    def _save(self, job: Job) -> None:
        snapshot = job.model_copy(deep=True)
        with self._lock:
            self._jobs[job.id] = snapshot
            if len(self._jobs) > MAX_JOBS_KEPT:
                oldest = sorted(self._jobs.values(), key=lambda j: j.created_at)[: len(self._jobs) - MAX_JOBS_KEPT]
                for old in oldest:
                    self._jobs.pop(old.id, None)

    def submit(self, job: Job, client_factory: Callable[[], MusicClient]) -> Future:
        self._save(job)

        def work() -> Job:
            try:
                client = client_factory()
            except Exception as exc:  # noqa: BLE001
                job.status, job.error = JobStatus.FAILED, f"No se pudo conectar con YouTube Music: {exc}"
                job.finished_at = datetime.now(timezone.utc)
                self._save(job)
                return job
            return run_job(job, client, self._save, self.batch_size, self.batch_delay)

        return self._executor.submit(work)

    def get(self, job_id: str, owner_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
        return job if job and job.owner_id == owner_id else None

    def list(self, owner_id: str) -> list[Job]:
        with self._lock:
            jobs = [j for j in self._jobs.values() if j.owner_id == owner_id]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
