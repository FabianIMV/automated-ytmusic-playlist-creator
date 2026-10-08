"""Autenticación: modo local (sin login) o Supabase (login con Google, etc.).

Con AUTH_MODE=supabase el frontend inicia sesión con supabase-js y envía
`Authorization: Bearer <access_token>`; aquí solo se verifica el JWT.
"""

from __future__ import annotations

from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from playlist_creator.config import Settings, get_settings

LOCAL_USER_ID = "local"

bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: str
    email: str | None = None
    name: str | None = None
    avatar_url: str | None = None


@lru_cache
def _jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json", cache_keys=True)


def verify_supabase_token(token: str, settings: Settings) -> dict:
    if not settings.supabase_url:
        raise RuntimeError("AUTH_MODE=supabase requiere SUPABASE_URL")
    issuer = f"{settings.supabase_url.rstrip('/')}/auth/v1"
    options = {"require": ["exp", "sub"]}
    if settings.supabase_jwt_secret:
        key, algorithms = settings.supabase_jwt_secret, ["HS256"]
    else:
        key = _jwks_client(settings.supabase_url).get_signing_key_from_jwt(token).key
        algorithms = ["RS256", "ES256"]
    return jwt.decode(
        token, key, algorithms=algorithms, audience=settings.supabase_jwt_audience, issuer=issuer, options=options
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if settings.auth_mode == "none":
        return CurrentUser(id=LOCAL_USER_ID, name="Local")

    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta el token (Authorization: Bearer ...)")
    try:
        claims = verify_supabase_token(credentials.credentials, settings)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token inválido: {exc}") from exc

    meta = claims.get("user_metadata") or {}
    return CurrentUser(
        id=claims["sub"],
        email=claims.get("email"),
        name=meta.get("full_name") or meta.get("name"),
        avatar_url=meta.get("avatar_url") or meta.get("picture"),
    )
