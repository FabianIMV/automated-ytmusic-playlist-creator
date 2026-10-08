"""Credenciales de YouTube Music (headers del navegador) y su almacenamiento.

Acepta lo que el usuario copie desde DevTools:
- "Copy as cURL (bash)" de Chrome/Edge/Firefox
- "Copy request headers" (líneas "clave: valor")
"""

from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path
from typing import Protocol

DEFAULT_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://music.youtube.com",
    "referer": "https://music.youtube.com/",
    "x-origin": "https://music.youtube.com",
    "x-youtube-bootstrap-logged-in": "true",
    "x-youtube-client-name": "67",
    "x-youtube-client-version": "1.20250811.03.00",
}

REQUIRED_HEADERS = ("authorization", "cookie")


class CredentialsError(ValueError):
    """El texto pegado no contiene credenciales utilizables."""


def _parse_curl(text: str) -> dict[str, str]:
    # Continúa líneas (bash "\" y cmd "^") y normaliza el quoting $'...' de Chrome
    text = re.sub(r"[\\^]\r?\n", " ", text).replace("$'", "'")
    try:
        tokens = shlex.split(text)
    except ValueError as exc:
        raise CredentialsError(f"No se pudo interpretar el cURL: {exc}") from exc

    headers: dict[str, str] = {}
    it = iter(tokens)
    for token in it:
        if token in ("-H", "--header"):
            raw = next(it, "")
            if ":" in raw:
                key, value = raw.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        elif token in ("-b", "--cookie"):
            headers["cookie"] = next(it, "").strip()
    return headers


def _parse_header_lines(text: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(":") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def parse_raw_credentials(text: str) -> dict[str, str]:
    """Convierte un cURL o un bloque de headers en el dict que espera ytmusicapi."""
    text = (text or "").strip()
    if not text:
        raise CredentialsError("El texto está vacío")

    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CredentialsError(f"JSON inválido: {exc}") from exc
        headers = {str(k).lower(): str(v) for k, v in data.items()}
    elif text.lower().startswith("curl"):
        headers = _parse_curl(text)
    else:
        headers = _parse_header_lines(text)

    missing = [h for h in REQUIRED_HEADERS if not headers.get(h)]
    if missing:
        raise CredentialsError(
            f"Faltan headers obligatorios: {', '.join(missing)}. "
            "Copia una petición POST a music.youtube.com/youtubei/v1/browse estando logueado."
        )
    if "SAPISID" not in headers["cookie"]:
        raise CredentialsError("La cookie no contiene SAPISID: asegúrate de haber iniciado sesión en YouTube Music")

    return {**DEFAULT_HEADERS, **headers}


# --- Almacenamiento --------------------------------------------------------

class CredentialStore(Protocol):
    def get(self, user_id: str) -> dict[str, str] | None: ...
    def set(self, user_id: str, headers: dict[str, str]) -> None: ...
    def delete(self, user_id: str) -> None: ...


class FileCredentialStore:
    """Guarda un JSON por usuario en `<data_dir>/credentials/` (permisos 600).

    Para multiusuario con Supabase se puede reemplazar por una implementación
    que use una tabla con RLS (ver docs/ARQUITECTURA.md).
    """

    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir) / "credentials"

    def _path(self, user_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", user_id)
        return self.dir / f"{safe}.json"

    def get(self, user_id: str) -> dict[str, str] | None:
        path = self._path(user_id)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def set(self, user_id: str, headers: dict[str, str]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self._path(user_id)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)  # el modo de os.open solo aplica al crear el archivo
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(headers, f, indent=2)

    def delete(self, user_id: str) -> None:
        self._path(user_id).unlink(missing_ok=True)
