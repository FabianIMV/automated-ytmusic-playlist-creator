"""Salud, usuario actual y conexión con YouTube Music."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from playlist_creator.api.auth import CurrentUser, get_current_user
from playlist_creator.api.deps import ClientFactory, get_client_factory, get_store
from playlist_creator.api.schemas import (
    CredentialsIn,
    GoogleConnectIn,
    Health,
    Me,
    YTMusicAccount,
    YTMusicStatus,
)
from playlist_creator.config import Settings, get_settings
from playlist_creator.core.credentials import CredentialsError, CredentialStore, parse_raw_credentials
from playlist_creator.core.youtube_api import google_credentials, is_google_credentials

router = APIRouter(prefix="/api", tags=["cuenta"])


def _check(creds: dict[str, str], client_factory: ClientFactory) -> YTMusicStatus:
    mode = "google" if is_google_credentials(creds) else "browser"
    try:
        info = client_factory(creds).account_info()
    except Exception as exc:  # noqa: BLE001
        prefix = "" if mode == "google" else "YouTube Music rechazó las credenciales: "
        return YTMusicStatus(connected=False, mode=mode, error=f"{prefix}{exc}")
    return YTMusicStatus(
        connected=True,
        mode=mode,
        account=YTMusicAccount(
            name=info.get("accountName"), handle=info.get("channelHandle"), photo_url=info.get("accountPhotoUrl")
        ),
    )


def _status(user: CurrentUser, store: CredentialStore, client_factory: ClientFactory) -> YTMusicStatus:
    creds = store.get(user.id)
    if not creds:
        return YTMusicStatus(connected=False)
    return _check(creds, client_factory)


@router.get("/health", response_model=Health)
def health(settings: Settings = Depends(get_settings)) -> Health:
    return Health(auth_mode=settings.auth_mode, google_connect=settings.google_connect_enabled)


@router.get("/me", response_model=Me)
def me(
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    store: CredentialStore = Depends(get_store),
    client_factory: ClientFactory = Depends(get_client_factory),
) -> Me:
    return Me(user=user, auth_mode=settings.auth_mode, ytmusic=_status(user, store, client_factory))


@router.get("/ytmusic/credentials", response_model=YTMusicStatus)
def credentials_status(
    user: CurrentUser = Depends(get_current_user),
    store: CredentialStore = Depends(get_store),
    client_factory: ClientFactory = Depends(get_client_factory),
) -> YTMusicStatus:
    return _status(user, store, client_factory)


@router.put("/ytmusic/credentials", response_model=YTMusicStatus)
def save_credentials(
    body: CredentialsIn,
    user: CurrentUser = Depends(get_current_user),
    store: CredentialStore = Depends(get_store),
    client_factory: ClientFactory = Depends(get_client_factory),
) -> YTMusicStatus:
    """Valida el cURL/headers contra YouTube Music y, si funcionan, los guarda para el usuario."""
    try:
        headers = parse_raw_credentials(body.raw)
    except CredentialsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    result = _check(headers, client_factory)
    if not result.connected:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, result.error)
    store.set(user.id, headers)
    return result


@router.put("/ytmusic/google", response_model=YTMusicStatus)
def connect_google(
    body: GoogleConnectIn,
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    store: CredentialStore = Depends(get_store),
    client_factory: ClientFactory = Depends(get_client_factory),
) -> YTMusicStatus:
    """Modo simple: guarda el refresh token de Google (scope youtube) y lo valida contra YouTube.

    Reemplaza una conexión previa por cURL (y viceversa): cada usuario usa un solo modo.
    """
    if not settings.google_connect_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El modo simple no está configurado en el servidor (faltan GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET)",
        )
    creds = google_credentials(body.refresh_token)
    result = _check(creds, client_factory)
    if not result.connected:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, result.error)
    store.set(user.id, creds)
    return result


@router.delete("/ytmusic/credentials", status_code=status.HTTP_204_NO_CONTENT)
def delete_credentials(
    user: CurrentUser = Depends(get_current_user), store: CredentialStore = Depends(get_store)
) -> Response:
    store.delete(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
