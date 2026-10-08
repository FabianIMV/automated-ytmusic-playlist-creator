"""Salud, usuario actual y conexión con YouTube Music."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from playlist_creator.api.auth import CurrentUser, get_current_user
from playlist_creator.api.deps import ClientFactory, get_client_factory, get_store
from playlist_creator.api.schemas import CredentialsIn, Health, Me, YTMusicAccount, YTMusicStatus
from playlist_creator.config import Settings, get_settings
from playlist_creator.core.credentials import CredentialsError, CredentialStore, parse_raw_credentials

router = APIRouter(prefix="/api", tags=["cuenta"])


def _check(headers: dict[str, str], client_factory: ClientFactory) -> YTMusicStatus:
    try:
        info = client_factory(headers).account_info()
    except Exception as exc:  # noqa: BLE001
        return YTMusicStatus(connected=False, error=f"YouTube Music rechazó las credenciales: {exc}")
    return YTMusicStatus(
        connected=True,
        account=YTMusicAccount(
            name=info.get("accountName"), handle=info.get("channelHandle"), photo_url=info.get("accountPhotoUrl")
        ),
    )


def _status(user: CurrentUser, store: CredentialStore, client_factory: ClientFactory) -> YTMusicStatus:
    headers = store.get(user.id)
    if not headers:
        return YTMusicStatus(connected=False)
    return _check(headers, client_factory)


@router.get("/health", response_model=Health)
def health(settings: Settings = Depends(get_settings)) -> Health:
    return Health(auth_mode=settings.auth_mode)


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


@router.delete("/ytmusic/credentials", status_code=status.HTTP_204_NO_CONTENT)
def delete_credentials(
    user: CurrentUser = Depends(get_current_user), store: CredentialStore = Depends(get_store)
) -> Response:
    store.delete(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
