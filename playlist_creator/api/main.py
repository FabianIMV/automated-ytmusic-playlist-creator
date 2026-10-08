"""App FastAPI. Ejecutar con:  uvicorn playlist_creator.api.main:app --reload"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from playlist_creator import __version__
from playlist_creator.api.auth import LOCAL_USER_ID
from playlist_creator.api.deps import ClientFactory
from playlist_creator.api.jobs import JobManager
from playlist_creator.api.routes import account, playlists
from playlist_creator.config import Settings, get_settings
from playlist_creator.core.credentials import CredentialStore, FileCredentialStore
from playlist_creator.core.music import YTMusicClient

log = logging.getLogger("playlist_creator")


def _import_legacy_headers(settings: Settings, store: CredentialStore) -> None:
    """Reutiliza el headers_auth.json que genera la CLI para el usuario local."""
    legacy = settings.legacy_headers_file
    if settings.auth_mode == "none" and legacy.exists() and not store.get(LOCAL_USER_ID):
        store.set(LOCAL_USER_ID, json.loads(legacy.read_text(encoding="utf-8")))
        log.info("Credenciales importadas desde %s", legacy)


def create_app(
    settings: Settings | None = None,
    credential_store: CredentialStore | None = None,
    client_factory: ClientFactory | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    store = credential_store or FileCredentialStore(settings.data_dir)
    jobs = JobManager(settings.job_workers, settings.batch_size, settings.batch_delay_seconds)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _import_legacy_headers(settings, store)
        yield
        jobs.shutdown()

    app = FastAPI(
        title="YouTube Music Playlist Creator",
        version=__version__,
        description="Crea playlists de YouTube Music desde setlists (texto, lista o setlist.fm).",
        lifespan=lifespan,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.credential_store = store
    app.state.jobs = jobs
    app.state.client_factory = client_factory or (
        lambda headers: YTMusicClient(headers, language=settings.ytmusic_language)
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(account.router)
    app.include_router(playlists.router)

    # Si el frontend está compilado, se sirve desde la misma app (un solo deploy).
    dist = settings.frontend_dist
    if (dist / "index.html").exists():

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path == "api" or path.startswith("api/"):
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Ruta no encontrada")
            file = (dist / path).resolve()
            if path and file.is_file() and file.is_relative_to(dist.resolve()):
                return FileResponse(file)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
