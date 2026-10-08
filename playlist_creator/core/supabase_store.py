"""Credenciales de YouTube Music guardadas en Supabase, cifradas.

Pensado para deploys con disco efímero (Render/Fly). Habla con la API REST de Supabase
(PostgREST) usando `requests`, sin el SDK. Los headers del navegador incluyen cookies de
Google (credenciales completas de la cuenta): se cifran con Fernet antes de salir del
backend, así que en la base solo hay texto cifrado. La tabla se crea con
supabase/migrations/20261008000000_ytmusic_credentials.sql.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import requests
from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("playlist_creator")

TABLE = "ytmusic_credentials"


class SupabaseCredentialStore:
    """Cumple el protocolo `CredentialStore`: una fila cifrada por usuario."""

    def __init__(self, url: str, service_key: str, encryption_key: str | bytes, timeout: float = 10.0):
        if not (url and service_key and encryption_key):
            raise ValueError("Se requieren la URL de Supabase, la clave secreta y la clave de cifrado")
        # Los PaaS suelen dejar espacios o saltos de línea al pegar variables de entorno.
        url, service_key = url.strip(), service_key.strip()
        try:
            self._fernet = Fernet(encryption_key)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "CREDENTIALS_ENCRYPTION_KEY no es una clave Fernet válida (32 bytes en base64 url-safe). "
                'Genera una con: python3 -c "import base64, os; '
                'print(base64.urlsafe_b64encode(os.urandom(32)).decode())"'
            ) from exc
        self.endpoint = f"{url.rstrip('/')}/rest/v1/{TABLE}"
        self.timeout = timeout
        # Las claves nuevas (sb_secret_...) viajan solo en `apikey`; las legacy (service_role,
        # un JWT que empieza con "eyJ") además como Bearer.
        self._headers = {"apikey": service_key}
        if service_key.startswith("eyJ"):
            self._headers["Authorization"] = f"Bearer {service_key}"

    # --- CredentialStore -------------------------------------------------

    def get(self, user_id: str) -> dict[str, str] | None:
        response = self._request("GET", params={"user_id": f"eq.{user_id}", "select": "data", "limit": "1"})
        if response.status_code == 404:
            # Normalmente la tabla no existe todavía (falta aplicar la migración).
            log.warning("Supabase respondió 404 al leer credenciales: %s", self._detail(response))
            return None
        self._check(response)
        rows = self._json(response)
        if not rows:
            return None
        return self._decrypt(rows[0]["data"])

    def set(self, user_id: str, headers: dict[str, str]) -> None:
        row = {
            "user_id": user_id,
            "data": self._fernet.encrypt(json.dumps(headers).encode("utf-8")).decode("ascii"),
            # El default de la columna solo aplica al insertar: al actualizar hay que enviarlo.
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        response = self._request(
            "POST", params={"on_conflict": "user_id"}, body=row, prefer="resolution=merge-duplicates"
        )
        self._check(response)

    def delete(self, user_id: str) -> None:
        self._check(self._request("DELETE", params={"user_id": f"eq.{user_id}"}))

    # --- Internos --------------------------------------------------------

    def _request(self, method: str, *, params: dict, body: dict | None = None, prefer: str | None = None):
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            return requests.request(
                method, self.endpoint, headers=headers, params=params, json=body, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"No se pudo conectar con Supabase: {exc}") from exc

    @staticmethod
    def _detail(response: requests.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            detail = body.get("message") or body.get("msg") or body.get("error_description") or body.get("error")
        else:
            detail = response.text
        return str(detail or "sin detalle")[:300]

    def _check(self, response: requests.Response) -> None:
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase respondió {response.status_code}: {self._detail(response)}")

    @staticmethod
    def _json(response: requests.Response):
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError("Supabase devolvió una respuesta que no es JSON") from exc

    def _decrypt(self, token: str) -> dict[str, str] | None:
        try:
            headers = json.loads(self._fernet.decrypt(token.encode("ascii")))
        except (InvalidToken, ValueError):
            # Clave de cifrado distinta a la usada al guardar (o dato corrupto): no hay forma de
            # recuperarlo, así que se trata como "sin credenciales" y el usuario las vuelve a pegar.
            log.warning("No se pudieron descifrar las credenciales guardadas (¿cambió CREDENTIALS_ENCRYPTION_KEY?)")
            return None
        return headers if isinstance(headers, dict) else None
