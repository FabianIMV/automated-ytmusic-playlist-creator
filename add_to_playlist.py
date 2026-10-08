#!/usr/bin/env python3
"""
Agrega canciones de un setlist a una playlist existente de YouTube Music.

Uso: python3 add_to_playlist.py <playlist_url_or_id> <setlist.txt>

Es un atajo de:
    python3 ytmusic_playlist_creator.py --file <setlist.txt> --playlist-id <playlist> --auto
así que usa el mismo flujo (búsqueda, deduplicación y lotes) que la CLI principal.
"""

import sys


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[0].strip():
        print("Usage: python3 add_to_playlist.py <playlist_url_or_id> <setlist.txt>")
        print(
            "Example: python3 add_to_playlist.py 'https://music.youtube.com/playlist?list=PL...' new_order_missing.txt"
        )
        return 1

    playlist, setlist_file = argv
    # Import tardío: así el mensaje de uso sale aunque falten dependencias.
    from ytmusic_playlist_creator import main as run_cli

    return run_cli(["--file", setlist_file, "--playlist-id", playlist, "--auto"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
