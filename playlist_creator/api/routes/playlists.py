"""Setlists, búsqueda, creación de playlists y seguimiento de jobs."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from fastapi.concurrency import run_in_threadpool

from playlist_creator.api.auth import CurrentUser, get_current_user
from playlist_creator.api.deps import ClientFactory, get_client_factory, get_jobs, get_store
from playlist_creator.api.jobs import JobManager
from playlist_creator.api.schemas import SearchResult
from playlist_creator.config import Settings, get_settings
from playlist_creator.core.builder import prepare_job
from playlist_creator.core.credentials import CredentialStore
from playlist_creator.core.sources import SourceError, load_source
from playlist_creator.models import Job, PlaylistRequest, Setlist, Source

router = APIRouter(prefix="/api", tags=["playlists"])


def _load(source: Source, settings: Settings) -> Setlist:
    try:
        setlist = load_source(source)
    except SourceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if len(setlist.songs) > settings.max_songs_per_job:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Máximo {settings.max_songs_per_job} canciones por playlist (llegaron {len(setlist.songs)})",
        )
    return setlist


@router.post("/setlists/parse", response_model=Setlist)
def parse_setlist(
    source: Source = Body(..., examples=[{"type": "text", "text": "Oasis - Wonderwall\nBlur - Song 2"}]),
    _: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Setlist:
    """Lee la fuente (texto, lista o URL de setlist.fm) sin tocar YouTube Music."""
    return _load(source, settings)


@router.get("/search", response_model=SearchResult)
def search(
    q: str = Query(..., min_length=1, description='Ej: "Oasis - Wonderwall"'),
    user: CurrentUser = Depends(get_current_user),
    store: CredentialStore = Depends(get_store),
    client_factory: ClientFactory = Depends(get_client_factory),
) -> SearchResult:
    """Busca la mejor coincidencia para una canción (usa las credenciales si existen)."""
    return SearchResult(query=q, track=client_factory(store.get(user.id)).search_track(q))


@router.post(
    "/playlists",
    response_model=Job,
    status_code=status.HTTP_202_ACCEPTED,
    responses={200: {"model": Job, "description": "Job terminado (cuando wait=true)"}},
)
async def create_playlist(
    body: PlaylistRequest,
    response: Response,
    wait: bool = Query(False, description="Esperar a que termine y devolver el resultado final (útil en Postman)"),
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    store: CredentialStore = Depends(get_store),
    jobs: JobManager = Depends(get_jobs),
    client_factory: ClientFactory = Depends(get_client_factory),
) -> Job:
    """Crea una playlist (o agrega a una existente con `playlist_id`). Devuelve un job para seguir el progreso."""
    # Las búsquedas también usan las credenciales si existen: sin sesión, YouTube Music
    # suele devolver solo videos (sobre todo desde IPs de servidores).
    headers = await run_in_threadpool(store.get, user.id)
    if not body.dry_run and not headers:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Primero conecta tu cuenta de YouTube Music (PUT /api/ytmusic/credentials) o usa dry_run=true",
        )

    setlist = await run_in_threadpool(_load, body.source, settings)
    job = jobs.new_job(
        owner_id=user.id,
        dry_run=body.dry_run,
        name=body.name,
        description=body.description,
        privacy=body.privacy,
        playlist_id=body.playlist_id,
    )
    prepare_job(job, setlist)
    future = jobs.submit(job, lambda: client_factory(headers))

    if not wait:
        return jobs.get(job.id, user.id)
    await asyncio.wrap_future(future)
    response.status_code = status.HTTP_200_OK
    return jobs.get(job.id, user.id)


@router.get("/jobs", response_model=list[Job], response_model_exclude={"__all__": {"items"}})
def list_jobs(user: CurrentUser = Depends(get_current_user), jobs: JobManager = Depends(get_jobs)) -> list[Job]:
    """Jobs del usuario, más recientes primero (sin el detalle por canción)."""
    return jobs.list(user.id)


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str, user: CurrentUser = Depends(get_current_user), jobs: JobManager = Depends(get_jobs)) -> Job:
    job = jobs.get(job_id, user.id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job no encontrado")
    return job
