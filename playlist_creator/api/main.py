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
from playlist_creator.core.music import MusicClient, YTMusicClient
from playlist_creator.core.supabase_store import SupabaseCredentialStore
from playlist_creator.core.youtube_api import YouTubeDataApiClient, is_google_credentials

log = logging.getLogger("playlist_creator")


def _import_legacy_headers(settings: Settings, store: CredentialStore) -> None:
    """Reutiliza el headers_auth.json que genera la CLI para el usuario local."""
    legacy = settings.legacy_headers_file
    if settings.auth_mode == "none" and legacy.exists() and not store.get(LOCAL_USER_ID):
        store.set(LOCAL_USER_ID, json.loads(legacy.read_text(encoding="utf-8")))
        log.info("Credenciales importadas desde %s", legacy)


def _build_store(settings: Settings) -> CredentialStore:
    if settings.credential_store == "file":
        return FileCredentialStore(settings.data_dir)

    required = {
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_SERVICE_KEY": settings.supabase_service_key,
        "CREDENTIALS_ENCRYPTION_KEY": settings.credentials_encryption_key,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"CREDENTIAL_STORE=supabase requiere definir: {', '.join(missing)}")
    return SupabaseCredentialStore(
        settings.supabase_url, settings.supabase_service_key, settings.credentials_encryption_key
    )


def _default_client_factory(settings: Settings) -> ClientFactory:
    """Elige el cliente según cómo se conectó el usuario: Google (Data API) o cURL (ytmusicapi)."""

    def factory(creds: dict[str, str] | None) -> MusicClient:
        if is_google_credentials(creds):
            if not settings.google_connect_enabled:
                raise RuntimeError("Faltan GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET en el servidor")
            return YouTubeDataApiClient(
                creds["refresh_token"],
                settings.google_client_id,
                settings.google_client_secret,
                language=settings.ytmusic_language,
            )
        return YTMusicClient(creds, language=settings.ytmusic_language)

    return factory


def create_app(
    settings: Settings | None = None,
    credential_store: CredentialStore | None = None,
    client_factory: ClientFactory | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    if settings.auth_mode == "supabase" and not settings.supabase_url:
        raise RuntimeError("AUTH_MODE=supabase requiere definir SUPABASE_URL")
    store = credential_store or _build_store(settings)
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
    app.state.client_factory = client_factory or _default_client_factory(settings)

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
