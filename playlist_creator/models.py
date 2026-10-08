"""Modelos compartidos entre el núcleo, la CLI y la API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class Privacy(str, Enum):
    PUBLIC = "PUBLIC"
    UNLISTED = "UNLISTED"
    PRIVATE = "PRIVATE"


# --- Fuentes de canciones -------------------------------------------------

class TextSource(BaseModel):
    """Texto libre: una canción por línea ("Artista - Canción"). Ignora vacías y '#'."""

    type: Literal["text"] = "text"
    text: str = Field(..., min_length=1)


class SongsSource(BaseModel):
    """Lista explícita de canciones (ideal para Postman / integraciones)."""

    type: Literal["songs"] = "songs"
    songs: list[str] = Field(..., min_length=1)


class SetlistFmSource(BaseModel):
    """URL de un setlist en setlist.fm."""

    type: Literal["setlistfm"] = "setlistfm"
    url: str = Field(..., pattern=r"^https?://(www\.)?setlist\.fm/.+")


Source = Annotated[Union[TextSource, SongsSource, SetlistFmSource], Field(discriminator="type")]


class Setlist(BaseModel):
    """Resultado de interpretar una fuente: canciones + metadatos sugeridos."""

    artist: str | None = None
    event_info: str | None = None
    songs: list[str]
    suggested_name: str
    suggested_description: str


# --- Resultados de búsqueda ----------------------------------------------

class Track(BaseModel):
    video_id: str
    title: str
    artists: list[str] = []
    album: str | None = None
    duration: str | None = None
    thumbnail: str | None = None
    result_type: str | None = None  # "song" | "video"


class ItemStatus(str, Enum):
    PENDING = "pending"
    FOUND = "found"            # encontrada (y agregada si no es dry run)
    DUPLICATE = "duplicate"    # ya estaba en la playlist / repetida en la lista
    NOT_FOUND = "not_found"
    ERROR = "error"


class ItemResult(BaseModel):
    index: int
    query: str
    status: ItemStatus = ItemStatus.PENDING
    track: Track | None = None
    error: str | None = None


# --- Petición de creación y estado del job --------------------------------

class PlaylistRequest(BaseModel):
    """Payload para crear una playlist o agregar canciones a una existente."""

    source: Source
    name: str | None = Field(None, max_length=150, description="Por defecto se sugiere desde la fuente")
    description: str | None = Field(None, max_length=5000)
    privacy: Privacy = Privacy.PUBLIC
    playlist_id: str | None = Field(
        None, description="ID o URL de una playlist existente: agrega ahí en vez de crear una nueva"
    )
    dry_run: bool = Field(False, description="Solo busca las canciones, no escribe nada en YouTube Music")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source": {"type": "songs", "songs": ["Oasis - Wonderwall", "Blur - Song 2"]},
                    "name": "Britpop 🎸",
                    "privacy": "PRIVATE",
                },
                {
                    "source": {
                        "type": "setlistfm",
                        "url": "https://www.setlist.fm/setlist/the-hives/2025/teatro-caupolican-santiago-chile-1234abcd.html",
                    },
                    "dry_run": True,
                },
            ]
        }
    }


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobSummary(BaseModel):
    total: int = 0
    processed: int = 0
    found: int = 0
    added: int = 0
    duplicates: int = 0
    not_found: int = 0
    errors: int = 0


class Job(BaseModel):
    id: str
    owner_id: str
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    dry_run: bool = False
    name: str | None = None
    description: str | None = None
    privacy: Privacy = Privacy.PUBLIC
    artist: str | None = None
    event_info: str | None = None
    playlist_id: str | None = None
    playlist_url: str | None = None
    summary: JobSummary = Field(default_factory=JobSummary)
    items: list[ItemResult] = []
    message: str | None = None
    error: str | None = None
