"""Dependencias compartidas por las rutas (se guardan en app.state al crear la app)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Request

from playlist_creator.api.jobs import JobManager
from playlist_creator.core.credentials import CredentialStore
from playlist_creator.core.music import MusicClient

# Recibe headers (o None para solo búsquedas) y devuelve un cliente de YouTube Music.
ClientFactory = Callable[[dict[str, str] | None], MusicClient]


def get_store(request: Request) -> CredentialStore:
    return request.app.state.credential_store


def get_jobs(request: Request) -> JobManager:
    return request.app.state.jobs


def get_client_factory(request: Request) -> ClientFactory:
    return request.app.state.client_factory
