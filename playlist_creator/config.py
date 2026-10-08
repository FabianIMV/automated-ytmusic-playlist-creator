"""Configuración por variables de entorno (o archivo .env)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "none": uso local sin login (todo pertenece al usuario "local").
    # "supabase": exige un JWT de Supabase (Authorization: Bearer <access_token>).
    auth_mode: Literal["none", "supabase"] = "none"
    supabase_url: str | None = None
    # Solo para proyectos con el JWT secret legacy (HS256). Si se omite, se valida con JWKS.
    supabase_jwt_secret: str | None = None
    supabase_jwt_audience: str = "authenticated"

    # Dónde se guardan las credenciales de YouTube Music de cada usuario:
    # "file" (data_dir, para uso local) o "supabase" (tabla cifrada, para deploys en la nube
    # donde el disco es efímero). Ver supabase/migrations/.
    credential_store: Literal["file", "supabase"] = "file"
    # Clave secreta del proyecto (sb_secret_... o service_role legacy). Solo en el backend.
    supabase_service_key: str | None = None
    # Clave Fernet para cifrar las credenciales en la base. Generar con:
    #   python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
    credentials_encryption_key: str | None = None

    data_dir: Path = Path("data")
    # headers_auth.json de la CLI: si existe, se importa para el usuario "local" al arrancar.
    legacy_headers_file: Path = Path("headers_auth.json")

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    frontend_dist: Path = Path("frontend/dist")

    batch_size: int = 50
    batch_delay_seconds: float = 3.0
    job_workers: int = 2
    max_songs_per_job: int = 1000
    ytmusic_language: str = "en"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
