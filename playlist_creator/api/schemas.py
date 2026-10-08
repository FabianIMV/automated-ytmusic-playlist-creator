"""Modelos propios de la API (los del dominio están en playlist_creator.models)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from playlist_creator import __version__
from playlist_creator.api.auth import CurrentUser
from playlist_creator.models import Track


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = __version__
    auth_mode: Literal["none", "supabase"]
    google_connect: bool = Field(False, description="Si está disponible el modo simple (Conectar con Google)")


class YTMusicAccount(BaseModel):
    name: str | None = None
    handle: str | None = None
    photo_url: str | None = None


class YTMusicStatus(BaseModel):
    connected: bool
    mode: Literal["google", "browser"] | None = Field(
        None, description='"google" = modo simple (YouTube Data API); "browser" = modo avanzado (cURL)'
    )
    account: YTMusicAccount | None = None
    error: str | None = Field(None, description="Por qué no hay conexión (p. ej. headers vencidos)")


class Me(BaseModel):
    user: CurrentUser
    auth_mode: Literal["none", "supabase"]
    ytmusic: YTMusicStatus


class CredentialsIn(BaseModel):
    raw: str = Field(
        ...,
        min_length=10,
        description="cURL copiado desde DevTools ('Copy as cURL') o los request headers en texto plano",
    )


class GoogleConnectIn(BaseModel):
    refresh_token: str = Field(
        ..., min_length=10, description="provider_refresh_token de la sesión de Supabase (login con scope youtube)"
    )


class SearchResult(BaseModel):
    query: str
    track: Track | None
