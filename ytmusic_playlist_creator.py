#!/usr/bin/env python3
"""
YouTube Music Playlist Creator (CLI).

Crea (o amplía) una playlist de YouTube Music a partir de un setlist de setlist.fm
o de un archivo de texto. La lógica vive en el paquete `playlist_creator`; este
archivo solo se encarga de la interacción por consola.

Uso:
    python3 ytmusic_playlist_creator.py                          # modo interactivo
    python3 ytmusic_playlist_creator.py -f setlist.txt -n "Mi playlist"
    python3 ytmusic_playlist_creator.py -u <url de setlist.fm> --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

try:
    from pydantic import ValidationError

    from playlist_creator.core.builder import not_found_queries, prepare_job, run_job
    from playlist_creator.core.credentials import CredentialsError, parse_raw_credentials
    from playlist_creator.core.music import YTMusicClient, extract_playlist_id
    from playlist_creator.core.sources import SourceError, load_source
    from playlist_creator.models import (
        ItemResult,
        ItemStatus,
        Job,
        JobStatus,
        Privacy,
        Setlist,
        SetlistFmSource,
        Source,
        TextSource,
    )
except ImportError as exc:
    print(f"❌ Missing dependency: {exc.name or exc}")
    print("💡 Install dependencies with: pip install -r requirements.txt")
    sys.exit(1)

PASTE_FILE = "paste.txt"  # cURL o headers copiados desde DevTools
HEADERS_FILE = "headers_auth.json"  # headers ya procesados, se reutilizan en la siguiente ejecución
FAILED_FILE = "failed_songs.txt"
DEFAULT_SETLIST_FILE = "setlist.txt"
BATCH_SIZE = 50
BATCH_DELAY = 3  # segundos entre lotes
CONFIRM_ANSWERS = ("y", "yes", "s", "si", "sí")
PRIVACY_CHOICES = {"1": Privacy.PUBLIC, "2": Privacy.UNLISTED, "3": Privacy.PRIVATE}


# --- Credenciales ----------------------------------------------------------


def print_credential_instructions() -> None:
    print("❌ No valid headers found!")
    print("\n📝 To get started:")
    print("1. Go to https://music.youtube.com in Chrome")
    print("2. Open DevTools (F12) → Network tab")
    print("3. Find any POST request to 'browse?key='")
    print("4. Right-click → Copy → Copy as cURL")
    print("5. Paste the entire cURL command into 'paste.txt'")
    print("6. Run this script again")


def save_headers(headers: dict[str, str]) -> None:
    """Guarda los headers con permisos 600: contienen las cookies de tu cuenta."""
    fd = os.open(HEADERS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(headers, f, indent=2)
    # El modo de os.open solo aplica al crear el archivo; si ya existía, lo corregimos.
    os.chmod(HEADERS_FILE, 0o600)


def load_headers() -> dict[str, str] | None:
    """Obtiene los headers desde paste.txt (si existe) o desde headers_auth.json.

    Devuelve None si no hay credenciales utilizables; los errores se muestran aquí.
    """
    if os.path.exists(PASTE_FILE):
        try:
            with open(PASTE_FILE, encoding="utf-8") as f:
                headers = parse_raw_credentials(f.read())
        except (CredentialsError, OSError) as exc:
            print(f"⚠️ Error reading {PASTE_FILE}: {exc}")
            return None
        try:
            save_headers(headers)
        except OSError as exc:
            print(f"⚠️ Could not save {HEADERS_FILE}: {exc}")  # los headers igual sirven
        print("📱 Using updated headers from paste.txt")
        return headers

    if os.path.exists(HEADERS_FILE):
        try:
            with open(HEADERS_FILE, encoding="utf-8") as f:
                headers = parse_raw_credentials(f.read())
        except (CredentialsError, OSError) as exc:
            print(f"⚠️ Error reading {HEADERS_FILE}: {exc}")
            return None
        print("🔑 Using saved headers from headers_auth.json")
        return headers

    return None


# --- Fuentes -----------------------------------------------------------------


def read_text_source(filename: str) -> TextSource | None:
    """Lee un archivo de texto (una canción por línea) y lo devuelve como TextSource."""
    try:
        with open(filename, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"❌ Error: File '{filename}' not found")
        print("💡 Create a 'setlist.txt' file with format:")
        print("   Artist - Song")
        print("   Oasis - Wonderwall")
        print("   Billy Idol - White Wedding")
        return None
    except (OSError, UnicodeDecodeError) as exc:
        print(f"❌ Error reading file: {exc}")
        return None
    if not text:  # TextSource exige texto no vacío
        print(f"❌ Error: '{filename}' is empty")
        return None
    return TextSource(text=text)


def build_url_source(url: str) -> SetlistFmSource | None:
    try:
        return SetlistFmSource(url=url)
    except ValidationError:
        print(f"❌ Invalid setlist.fm URL: {url}")
        print("💡 Expected something like https://www.setlist.fm/setlist/...")
        return None


def fetch_setlist(source: Source) -> Setlist | None:
    try:
        return load_source(source)
    except SourceError as exc:
        print(f"❌ {exc}")
        return None


def print_preview(setlist: Setlist) -> None:
    print(f"\n📋 Setlist preview ({len(setlist.songs)} songs):")
    for i, song in enumerate(setlist.songs[:5], 1):
        print(f"   {i}. {song}")
    if len(setlist.songs) > 5:
        print(f"   ... and {len(setlist.songs) - 5} more songs")


# --- Progreso y reporte ------------------------------------------------------


def _track_label(item: ItemResult) -> str:
    track = item.track
    artist = track.artists[0] if track and track.artists else "Unknown"
    return f"{artist} - {track.title}"


def describe_item(item: ItemResult) -> str:
    if item.status == ItemStatus.FOUND:
        return f"✅ Found: {_track_label(item)}"
    if item.status == ItemStatus.DUPLICATE:
        return f"⏭️  Duplicate skipped: {_track_label(item)}"
    if item.status == ItemStatus.NOT_FOUND:
        return "❌ Not found"
    return f"⚠️  Error: {item.error}"


class ConsoleProgress:
    """Callback `on_update` de `run_job`: imprime cada canción una sola vez,
    cuando deja de estar `pending`, y avisa cada vez que se agrega un lote."""

    def __init__(self, batch_size: int, announce_created: bool) -> None:
        self.batch_size = batch_size
        self.announce_created = announce_created
        self._printed: set[int] = set()
        self._added = 0
        self._playlist_announced = False

    def __call__(self, job: Job) -> None:
        if self.announce_created and job.playlist_id and not self._playlist_announced:
            self._playlist_announced = True
            print(f"✅ Playlist created with ID: {job.playlist_id}")

        total = len(job.items)
        for item in job.items:
            if item.status == ItemStatus.PENDING or item.index in self._printed:
                continue
            self._printed.add(item.index)
            self._print_item(item, total)

        if job.summary.added != self._added:
            delta = job.summary.added - self._added
            self._added = job.summary.added
            print(f"  📤 Added {delta} new songs (total added this run: {self._added})")

    def _print_item(self, item: ItemResult, total: int) -> None:
        if item.index % self.batch_size == 0:
            batch_num = item.index // self.batch_size + 1
            total_batches = (total + self.batch_size - 1) // self.batch_size
            print(f"\n── Batch {batch_num}/{total_batches} ──")
        print(f"  [{item.index + 1}/{total}] {item.query}")
        print(f"    {describe_item(item)}")


def print_report(job: Job, created: bool) -> int:
    """Muestra el resumen final, guarda las no encontradas y devuelve el código de salida."""
    if job.status == JobStatus.FAILED:
        print(f"\n💥 Error: {job.error}")
        if job.playlist_url:
            print(f"🔗 Playlist URL: {job.playlist_url}")
        return 1

    s = job.summary
    print()
    if job.dry_run:
        print(f"✅ Songs found (dry run): {s.found}")
    else:
        print(f"✅ New songs added: {s.added}")
    print(f"⏭️  Duplicates skipped: {s.duplicates}")
    print(f"❌ Not found: {s.not_found}")
    if s.errors:
        print(f"⚠️  Errors: {s.errors}")
        for item in job.items:
            if item.status == ItemStatus.ERROR:
                print(f"   - {item.query}: {item.error}")

    missing = not_found_queries(job)
    if missing:
        if job.dry_run:
            print(f"\n⚠️  {len(missing)} songs not found (dry run: failed_songs.txt not written)")
        else:
            with open(FAILED_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(missing) + "\n")
            print(f"\n⚠️  {len(missing)} songs not found — saved to failed_songs.txt")
            print(
                f"   Retry with: python3 ytmusic_playlist_creator.py -f failed_songs.txt --playlist-id {job.playlist_id}"
            )

    if job.dry_run:
        print("\n🔎 Dry run finished: nothing was written to YouTube Music.")
        return 0

    if created:
        print(f"\n🎉 Playlist '{job.name}' created successfully!")
    print(f"\n🔗 Playlist URL: {job.playlist_url}")
    print(
        f"\n💡 To add more songs, run: python3 ytmusic_playlist_creator.py -f failed_songs.txt --playlist-id {job.playlist_id}"
    )
    return 0


# --- CLI ---------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="YouTube Music Playlist Creator",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--file", "-f", type=str, help="Setlist txt file (e.g. setlist.txt)")
    parser.add_argument("--url", "-u", type=str, help="setlist.fm URL")
    parser.add_argument("--name", "-n", type=str, help="Playlist name")
    parser.add_argument("--description", "-d", type=str, help="Playlist description")
    parser.add_argument(
        "--privacy",
        "-p",
        type=str,
        default="PUBLIC",
        choices=["PUBLIC", "UNLISTED", "PRIVATE"],
        help="Playlist privacy (default: PUBLIC)",
    )
    parser.add_argument(
        "--playlist-id",
        type=str,
        default=None,
        help="ID or URL of an existing playlist: add songs there instead of creating a new one",
    )
    parser.add_argument(
        "--auto", "-a", action="store_true", help="Non-interactive mode: skip all prompts, use defaults"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Only search for the songs: do not create or modify any playlist"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Con --file o --url no hay preguntas: se activa el modo automático.
    if args.file or args.url:
        args.auto = True
    if args.playlist_id is not None and not extract_playlist_id(args.playlist_id):
        print("❌ --playlist-id is empty")
        return 1

    print("🎸 YouTube Music Playlist Creator")
    print("=" * 50)
    if args.dry_run:
        print("🔎 Dry run: solo busca canciones, no escribe en YouTube Music")

    headers = load_headers()
    if headers is None and not args.dry_run:
        print_credential_instructions()
        return 1
    if headers is None:
        print("ℹ️  Sin credenciales: la búsqueda será sin sesión (resultados pueden ser menos precisos)")

    if not args.auto:
        print("1. Create from setlist.fm URL")
        print("2. Create from txt file")
        print("=" * 50)
        choice = input("\nChoose option [1/2]: ").strip()
    else:
        choice = "1" if args.url else "2"

    if choice == "1":
        url = args.url or input("\n🔗 Enter setlist.fm URL: ").strip()
        if not url:
            print("❌ URL required")
            return 1
        source = build_url_source(url)
        if source is None:
            return 1
        print(f"🌐 Fetching setlist from: {url}")
        setlist = fetch_setlist(source)
        if setlist is None:
            return 1
        print(f"✅ Found {len(setlist.songs)} songs from {setlist.artist or 'unknown artist'}")
        if setlist.event_info:
            print(f"📍 Event: {setlist.event_info}")

    elif choice == "2":
        filename = args.file or input("\n📁 Enter filename [setlist.txt]: ").strip() or DEFAULT_SETLIST_FILE
        source = read_text_source(filename)
        if source is None:
            return 1
        setlist = fetch_setlist(source)
        if setlist is None:
            return 1
        print(f"📁 Read {len(setlist.songs)} songs from {filename}")

    else:
        print("❌ Invalid option")
        return 1

    print_preview(setlist)

    # Configuración de la playlist
    print("\n🎵 Playlist Configuration")
    print("-" * 50)

    default_name = setlist.suggested_name
    if args.auto and args.name:
        playlist_name = args.name
    elif args.auto:
        playlist_name = default_name
        print(f"Playlist name: {playlist_name}")
    else:
        playlist_name = input(f"Playlist name [{default_name}]: ").strip() or default_name

    print("\nDefault description:")
    print(setlist.suggested_description)
    print()

    if args.auto and args.description:
        description = args.description
    elif args.auto:
        description = setlist.suggested_description
    else:
        custom_desc = input("Custom description (leave empty to use default): ").strip()
        description = custom_desc or setlist.suggested_description

    # Privacidad
    print("\n🔒 Privacy options:")
    print("1. PUBLIC (anyone can find and view)")
    print("2. UNLISTED (only people with link can view)")
    print("3. PRIVATE (only you can view)")
    if args.auto:
        privacy = Privacy(args.privacy)
        print(f"Privacy: {privacy.value}")
    else:
        privacy = PRIVACY_CHOICES.get(input("Choose privacy [1/2/3]: ").strip(), Privacy.PUBLIC)

    # Confirmación
    print("\n📝 Summary:")
    print(f"   Name: {playlist_name}")
    print(f"   Songs: {len(setlist.songs)}")
    print(f"   Privacy: {privacy.value}")
    if args.dry_run:
        print("   Mode: dry run (no playlist will be created or modified)")
    print()

    if not args.auto:
        question = "Search songs? [y/N]: " if args.dry_run else "Create playlist? [y/N]: "
        if input(question).strip().lower() not in CONFIRM_ANSWERS:
            print("❌ Operation cancelled")
            return 0

    # Ejecución
    existing_id = extract_playlist_id(args.playlist_id) if args.playlist_id else None
    job = Job(
        id=uuid.uuid4().hex,
        owner_id="cli",
        created_at=datetime.now(timezone.utc),
        dry_run=args.dry_run,
        name=playlist_name,
        description=description,
        privacy=privacy,
        playlist_id=existing_id,
    )
    prepare_job(job, setlist)

    try:
        client = YTMusicClient(headers)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo al iniciar ytmusicapi
        print(f"💥 Error creating YouTube Music client: {exc}")
        return 1

    created = existing_id is None and not args.dry_run
    if existing_id:
        print(f"📌 Adding to existing playlist: {existing_id}")
    elif created:
        print(f"🎵 Creating playlist: {playlist_name}")
        print(f"🔓 Privacy: {privacy.value}")

    action = "Searching" if args.dry_run else "Searching and adding"
    print(f"\n🔍 {action} {len(setlist.songs)} songs in batches of {BATCH_SIZE}...")

    progress = ConsoleProgress(batch_size=BATCH_SIZE, announce_created=created)
    run_job(job, client, on_update=progress, batch_size=BATCH_SIZE, batch_delay=BATCH_DELAY)
    return print_report(job, created=created)


if __name__ == "__main__":
    sys.exit(main())
