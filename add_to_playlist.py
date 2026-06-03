#!/usr/bin/env python3
"""
Add songs to an existing YouTube Music playlist
Usage: python3 add_to_playlist.py <playlist_url_or_id> <setlist.txt>
"""
import sys
import os
import json
from ytmusicapi import YTMusic


def setup_ytmusic():
    if os.path.exists('headers_auth.json'):
        return YTMusic('headers_auth.json')
    print("❌ No headers_auth.json found. Run your main script first to generate it.")
    sys.exit(1)


def extract_playlist_id(url_or_id):
    """Extract playlist ID from URL or return as-is if already an ID"""
    if 'list=' in url_or_id:
        return url_or_id.split('list=')[-1].split('&')[0]
    return url_or_id.strip()


def read_setlist(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
    print(f"📁 {len(lines)} songs loaded from {filename}")
    return lines


def add_songs_to_playlist(playlist_id, setlist):
    ytmusic = setup_ytmusic()

    print(f"\n🔍 Searching {len(setlist)} songs...")
    video_ids = []
    failed = []

    for i, song in enumerate(setlist, 1):
        print(f"  [{i}/{len(setlist)}] {song}")
        try:
            results = ytmusic.search(song, limit=5)
            found = False
            for r in results:
                if r.get('resultType') == 'song' and r.get('videoId'):
                    video_ids.append(r['videoId'])
                    artist = (r.get('artists') or [{}])[0].get('name', '?')
                    print(f"    ✅ {artist} - {r.get('title', '?')}")
                    found = True
                    break
            if not found:
                # fallback: try video type
                for r in results:
                    if r.get('videoId'):
                        video_ids.append(r['videoId'])
                        print(f"    ⚠️  Fallback (video): {r.get('title', '?')}")
                        found = True
                        break
            if not found:
                print(f"    ❌ Not found")
                failed.append(song)
        except Exception as e:
            print(f"    ❌ Error: {e}")
            failed.append(song)

    if not video_ids:
        print("\n❌ No songs found, nothing to add.")
        return

    print(f"\n📤 Adding {len(video_ids)} songs to playlist {playlist_id}...")
    try:
        ytmusic.add_playlist_items(playlist_id, video_ids)
        print(f"✅ Done! Added {len(video_ids)} songs.")
    except Exception as e:
        print(f"⚠️  Bulk add failed ({e}), trying one by one...")
        ok = 0
        for vid in video_ids:
            try:
                ytmusic.add_playlist_items(playlist_id, [vid])
                ok += 1
            except Exception as e2:
                print(f"  ❌ {vid}: {e2}")
        print(f"✅ Added {ok}/{len(video_ids)} songs individually.")

    if failed:
        print(f"\n❌ Still not found ({len(failed)}):")
        for s in failed:
            print(f"   - {s}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 add_to_playlist.py <playlist_url_or_id> <setlist.txt>")
        print("Example: python3 add_to_playlist.py 'https://music.youtube.com/playlist?list=PL...' new_order_missing.txt")
        sys.exit(1)

    playlist_id = extract_playlist_id(sys.argv[1])
    setlist_file = sys.argv[2]

    print(f"🎵 Target playlist ID: {playlist_id}")

    setlist = read_setlist(setlist_file)
    if not setlist:
        sys.exit(1)

    add_songs_to_playlist(playlist_id, setlist)