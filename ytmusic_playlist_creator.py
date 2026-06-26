#!/usr/bin/env python3
"""
YouTube Music Playlist Creator
Automates playlist creation in YouTube Music using ytmusicapi
Supports both txt files and setlist.fm URLs
"""

import json
import os
import re
import time
import argparse
from ytmusicapi import YTMusic
try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

def setup_ytmusic():
    """Setup ytmusicapi with your headers"""
    # Check if there's a paste.txt file with updated curl
    if os.path.exists('paste.txt'):
        try:
            headers = extract_headers_from_curl('paste.txt')
            if headers:
                print("📱 Using updated headers from paste.txt")
                with open('headers_auth.json', 'w') as f:
                    json.dump(headers, f, indent=2)
                return YTMusic('headers_auth.json')
        except Exception as e:
            print(f"⚠️ Error reading paste.txt: {e}")
    
    # If no paste.txt or error, show instructions
    print("❌ No valid headers found!")
    print("\n📝 To get started:")
    print("1. Go to https://music.youtube.com in Chrome")
    print("2. Open DevTools (F12) → Network tab")
    print("3. Find any POST request to 'browse?key='")
    print("4. Right-click → Copy → Copy as cURL")
    print("5. Paste the entire cURL command into 'paste.txt'")
    print("6. Run this script again")
    return None

def extract_headers_from_curl(filename):
    """Extract headers from a curl command file - improved version"""
    try:
        with open(filename, 'r') as f:
            curl_content = f.read()
        
        headers = {}
        # Split by both backslashes and newlines to handle multiline curl commands
        lines = curl_content.replace('\\\n', '\n').split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Process headers (-H)
            if line.startswith('-H'):
                # Extract header value between quotes
                match = re.search(r'-H\s+[\'"]([^\'"]*)[\'"]', line)
                if match:
                    header_content = match.group(1)
                    # Parse header
                    if ':' in header_content:
                        key, value = header_content.split(':', 1)
                        headers[key.strip().lower()] = value.strip()
            
            # Process cookies (-b)
            elif line.startswith('-b'):
                match = re.search(r'-b\s+[\'"]([^\'"]*)[\'"]', line)
                if match:
                    headers['cookie'] = match.group(1)
        
        # Debug: show found headers
        print(f"🔍 Headers found: {list(headers.keys())}")
        
        # Check critical headers
        critical_headers = ['authorization', 'cookie']
        missing = [h for h in critical_headers if h not in headers]
        
        if missing:
            print(f"❌ Missing critical headers: {missing}")
            print("💡 Make sure the curl command is complete in paste.txt")
            return None
        
        # Add default headers if missing
        defaults = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://music.youtube.com',
            'referer': 'https://music.youtube.com/',
            'x-origin': 'https://music.youtube.com',
            'x-youtube-bootstrap-logged-in': 'true',
            'x-youtube-client-name': '67',
            'x-youtube-client-version': '1.20250811.03.00'
        }
        
        for key, value in defaults.items():
            if key not in headers:
                headers[key] = value
        
        print(f"✅ Headers processed successfully ({len(headers)} total)")
        return headers
        
    except Exception as e:
        print(f"❌ Error processing paste.txt: {e}")
        print("💡 Verify the file contains a valid curl command")
        return None

def scrape_setlist_from_url(url):
    """
    Scrape setlist from setlist.fm URL
    
    Args:
        url (str): setlist.fm URL
        
    Returns:
        tuple: (artist, event_info, setlist) or (None, None, None)
    """
    if requests is None or BeautifulSoup is None:
        print("❌ Missing dependencies for URL scraping")
        print("💡 Install with: pip3 install requests beautifulsoup4")
        return None, None, None
    
    try:
        print(f"🌐 Fetching setlist from: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Get artist name - try multiple selectors
        artist = "Unknown Artist"
        
        # Try meta tag first
        meta_artist = soup.find('meta', property='og:title')
        if meta_artist:
            title_text = meta_artist.get('content', '')
            # Format: "Artist Setlist at ..."
            if ' Setlist' in title_text:
                artist = title_text.split(' Setlist')[0].strip()
        
        # Try header
        if artist == "Unknown Artist":
            artist_link = soup.find('a', class_='summary url')
            if artist_link:
                artist = artist_link.get_text(strip=True)
        
        # Try alternative header
        if artist == "Unknown Artist":
            artist_elem = soup.find('span', itemprop='name')
            if artist_elem:
                artist = artist_elem.get_text(strip=True)
        
        # Get event info (venue, city, date)
        venue = ""
        venue_elem = soup.find('a', class_='url fn')
        if venue_elem:
            venue = venue_elem.get_text(strip=True)
        
        date = ""
        date_elem = soup.find('em', class_='link')
        if date_elem:
            date = date_elem.get_text(strip=True)
        
        event_info = f"{venue} - {date}" if venue and date else venue or date
        
        # Get songs
        setlist = []
        song_elements = soup.find_all('a', class_='songLabel')
        
        for song_elem in song_elements:
            song_name = song_elem.get_text(strip=True)
            if song_name and not song_name.startswith('('):  # Skip annotations
                setlist.append(f"{artist} - {song_name}")
        
        print(f"✅ Found {len(setlist)} songs from {artist}")
        if event_info:
            print(f"📍 Event: {event_info}")
        
        return artist, event_info, setlist
        
    except Exception as e:
        print(f"❌ Error scraping URL: {str(e)}")
        return None, None, None

def search_song(ytmusic, song):
    """Search for a song, with fallback strategies. Returns the BEST match."""
    # Strategy 1: general search, pick first resultType==song
    try:
        results = ytmusic.search(song, limit=10)
        for r in results:
            if r.get('resultType') == 'song' and r.get('videoId'):
                return r
    except Exception:
        pass
    # Strategy 2: songs filter
    try:
        results = ytmusic.search(song, filter='songs', limit=5)
        for r in results:
            if r.get('videoId'):
                return r
    except Exception:
        pass
    # Strategy 3: videos filter
    try:
        results = ytmusic.search(song, filter='videos', limit=5)
        for r in results:
            if r.get('videoId'):
                return r
    except Exception:
        pass
    return None


def get_existing_video_ids(ytmusic, playlist_id):
    """Return the set of videoIds already present in a playlist."""
    existing = set()
    try:
        data = ytmusic.get_playlist(playlist_id, limit=None)
        for track in data.get('tracks', []):
            vid = track.get('videoId')
            if vid:
                existing.add(vid)
    except Exception as e:
        print(f"⚠️  Could not read existing playlist tracks: {e}")
    return existing


def add_songs_to_playlist(ytmusic, playlist_id, setlist, playlist_name="playlist"):
    """Search and add songs to an existing playlist in batches, skipping duplicates."""
    successful_adds = 0
    duplicate_skips = 0
    failed_songs = []
    total_added = 0

    # Track videoIds already in the playlist to avoid duplicates
    used_ids = get_existing_video_ids(ytmusic, playlist_id)
    print(f"📋 Playlist already has {len(used_ids)} unique tracks")

    batch_size = 50
    batch_delay = 3
    total_batches = (len(setlist) + batch_size - 1) // batch_size

    print(f"\n🔍 Searching and adding {len(setlist)} songs in batches of {batch_size}...")

    for batch_num, batch_start in enumerate(range(0, len(setlist), batch_size), 1):
        batch_songs = setlist[batch_start:batch_start + batch_size]
        video_ids = []

        print(f"\n── Batch {batch_num}/{total_batches}: searching {len(batch_songs)} songs ──")
        for i, song in enumerate(batch_songs, batch_start + 1):
            print(f"  [{i}/{len(setlist)}] {song}")
            result = search_song(ytmusic, song)
            if result:
                video_id = result.get('videoId')
                song_title = result.get('title', 'Unknown')
                artist_data = result.get('artists', [{}])
                artist = artist_data[0].get('name', 'Unknown') if artist_data else 'Unknown'
                if video_id in used_ids:
                    print(f"    ⏭️  Duplicate skipped: {artist} - {song_title}")
                    duplicate_skips += 1
                else:
                    used_ids.add(video_id)
                    video_ids.append(video_id)
                    print(f"    ✅ Found: {artist} - {song_title}")
                    successful_adds += 1
            else:
                print(f"    ❌ Not found")
                failed_songs.append(song)

        if video_ids:
            try:
                ytmusic.add_playlist_items(playlist_id, video_ids, duplicates=False)
                total_added += len(video_ids)
                print(f"  📤 Added {len(video_ids)} new songs (total added this run: {total_added})")
            except Exception as e:
                print(f"  ❌ Failed to add batch {batch_num}: {str(e)}")

        if batch_num < total_batches:
            print(f"  ⏳ Waiting {batch_delay}s before next batch...")
            time.sleep(batch_delay)

    # Save failed songs to file for retry
    if failed_songs:
        with open('failed_songs.txt', 'w', encoding='utf-8') as f:
            for song in failed_songs:
                f.write(song + '\n')
        print(f"\n⚠️  {len(failed_songs)} songs not found — saved to failed_songs.txt")
        print(f"   Retry with: python3 ytmusic_playlist_creator.py -f failed_songs.txt --playlist-id {playlist_id}")

    print(f"\n✅ New songs added: {successful_adds}")
    print(f"⏭️  Duplicates skipped: {duplicate_skips}")
    print(f"❌ Not found: {len(failed_songs)}")
    print(f"🎵 Playlist now has {len(used_ids)} unique tracks")
    return playlist_id


def create_playlist_from_setlist(setlist, playlist_name, description="", privacy="PUBLIC", existing_playlist_id=None):
    """
    Create a YouTube Music playlist from a list of songs
    
    Args:
        setlist (list): List of strings with format "Artist - Song"
        playlist_name (str): Name of the playlist
        description (str): Optional description
        privacy (str): Playlist privacy: "PUBLIC", "PRIVATE", or "UNLISTED"
    """
    try:
        # Initialize YouTube Music
        ytmusic = setup_ytmusic()
        
        if not ytmusic:
            return None
        
        if existing_playlist_id:
            playlist_id = existing_playlist_id
            print(f"📌 Adding to existing playlist: {playlist_id}")
        else:
            print(f"🎵 Creating playlist: {playlist_name}")
            print(f"🔓 Privacy: {privacy}")
            try:
                playlist_id = ytmusic.create_playlist(
                    playlist_name,
                    description,
                    privacy_status=privacy
                )
            except TypeError:
                print("⚠️ Privacy parameter not supported, creating playlist without privacy setting")
                playlist_id = ytmusic.create_playlist(playlist_name, description)
            print(f"✅ Playlist created with ID: {playlist_id}")

        add_songs_to_playlist(ytmusic, playlist_id, setlist, playlist_name)

        if not existing_playlist_id:
            print(f"\n🎉 Playlist '{playlist_name}' created successfully!")

        return playlist_id
        
    except Exception as e:
        print(f"💥 Error creating playlist: {str(e)}")
        return None

def read_setlist_from_file(filename="setlist.txt"):
    """
    Read setlist from a text file
    
    Args:
        filename (str): Name of the file with the setlist
        
    Returns:
        list: List of songs in format "Artist - Song"
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Filter empty lines and clean spaces
        setlist = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):  # Ignore empty lines and comments
                setlist.append(line)
        
        print(f"📁 Read {len(setlist)} songs from {filename}")
        return setlist
        
    except FileNotFoundError:
        print(f"❌ Error: File '{filename}' not found")
        print("💡 Create a 'setlist.txt' file with format:")
        print("   Artist - Song")
        print("   Oasis - Wonderwall")
        print("   Billy Idol - White Wedding")
        return []
    except Exception as e:
        print(f"❌ Error reading file: {str(e)}")
        return []

def main():
    """Main function - interactive mode or CLI mode"""

    parser = argparse.ArgumentParser(
        description='YouTube Music Playlist Creator',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--file', '-f', type=str, help='Setlist txt file (e.g. setlist.txt)')
    parser.add_argument('--url', '-u', type=str, help='setlist.fm URL')
    parser.add_argument('--name', '-n', type=str, help='Playlist name')
    parser.add_argument('--description', '-d', type=str, help='Playlist description')
    parser.add_argument('--privacy', '-p', type=str, default='PUBLIC',
                        choices=['PUBLIC', 'UNLISTED', 'PRIVATE'], help='Playlist privacy (default: PUBLIC)')
    parser.add_argument('--playlist-id', type=str, default=None,
                        help='Add songs to an existing playlist instead of creating a new one')
    parser.add_argument('--auto', '-a', action='store_true',
                        help='Non-interactive mode: skip all prompts, use defaults')
    args = parser.parse_args()

    # If CLI args provided, run in auto mode
    if args.file or args.url:
        args.auto = True

    print("🎸 YouTube Music Playlist Creator")
    print("=" * 50)

    if not args.auto:
        print("1. Create from setlist.fm URL")
        print("2. Create from txt file")
        print("=" * 50)

    choice = None
    if args.auto:
        choice = "1" if args.url else "2"
    else:
        choice = input("\nChoose option [1/2]: ").strip()
    
    setlist = []
    artist = ""
    event_info = ""
    
    if choice == "1":
        # URL mode
        if args.auto and args.url:
            url = args.url
        else:
            url = input("\n🔗 Enter setlist.fm URL: ").strip()
        if not url:
            print("❌ URL required")
            return
        artist, event_info, setlist = scrape_setlist_from_url(url)
        if not setlist:
            return

    elif choice == "2":
        # File mode
        if args.auto and args.file:
            filename = args.file
        else:
            filename = input("\n📁 Enter filename [setlist.txt]: ").strip()
        if not filename:
            filename = "setlist.txt"
        setlist = read_setlist_from_file(filename)
        if not setlist:
            return
        if setlist and ' - ' in setlist[0]:
            artist = setlist[0].split(' - ')[0]
    else:
        print("❌ Invalid option")
        return
    
    # Show setlist preview
    print(f"\n📋 Setlist preview ({len(setlist)} songs):")
    for i, song in enumerate(setlist[:5], 1):
        print(f"   {i}. {song}")
    if len(setlist) > 5:
        print(f"   ... and {len(setlist) - 5} more songs")
    
    # Playlist configuration
    print(f"\n🎵 Playlist Configuration")
    print("-" * 50)
    
    default_name = f"{artist} - Concert Setlist" if artist else "Concert Setlist"
    if args.auto and args.name:
        playlist_name = args.name
    elif args.auto:
        playlist_name = default_name
        print(f"Playlist name: {playlist_name}")
    else:
        playlist_name = input(f"Playlist name [{default_name}]: ").strip()
        if not playlist_name:
            playlist_name = default_name
    
    # Bilingual description with keywords
    keywords_en = "live concert setlist tour performance rock music playlist"
    keywords_es = "concierto en vivo setlist gira presentación música rock playlist"
    
    description_parts = [
        f"🎸 {artist} Concert Setlist" if artist else "Concert Setlist",
        f"📍 {event_info}" if event_info else "",
        f"🎵 {len(setlist)} songs",
        "",
        f"Keywords: {keywords_en}",
        f"Palabras clave: {keywords_es}",
    ]
    
    default_description = "\n".join([p for p in description_parts if p])
    
    print(f"\nDefault description:")
    print(default_description)
    print()
    
    if args.auto and args.description:
        description = args.description
    elif args.auto:
        description = default_description
    else:
        custom_desc = input("Custom description (leave empty to use default): ").strip()
        description = custom_desc if custom_desc else default_description
    
    # Privacy setting
    print("\n🔒 Privacy options:")
    print("1. PUBLIC (anyone can find and view)")
    print("2. UNLISTED (only people with link can view)")
    print("3. PRIVATE (only you can view)")
    
    if args.auto:
        privacy = args.privacy
        print(f"Privacy: {privacy}")
    else:
        privacy_choice = input("Choose privacy [1/2/3]: ").strip()
        privacy_map = {"1": "PUBLIC", "2": "UNLISTED", "3": "PRIVATE"}
        privacy = privacy_map.get(privacy_choice, "PUBLIC")
    
    # Confirm before creating
    print(f"\n📝 Summary:")
    print(f"   Name: {playlist_name}")
    print(f"   Songs: {len(setlist)}")
    print(f"   Privacy: {privacy}")
    print()
    
    if not args.auto:
        confirm = input(f"Create playlist? [y/N]: ").strip().lower()
        if confirm not in ['y', 'yes', 's', 'si', 'sí']:
            print("❌ Operation cancelled")
            return
    
    # Create or update playlist
    playlist_id = create_playlist_from_setlist(
        setlist,
        playlist_name,
        description,
        privacy,
        existing_playlist_id=args.playlist_id
    )

    if playlist_id:
        print(f"\n🔗 Playlist URL: https://music.youtube.com/playlist?list={playlist_id}")
        print(f"\n💡 To add more songs, run: python3 ytmusic_playlist_creator.py -f failed_songs.txt --playlist-id {playlist_id}")

def quick_create(url_or_file, playlist_name=None, privacy="PUBLIC"):
    """
    Quick playlist creation (for advanced users)
    
    Args:
        url_or_file: URL from setlist.fm or path to txt file
        playlist_name: Optional custom name
        privacy: "PUBLIC", "UNLISTED", or "PRIVATE"
    """
    setlist = []
    artist = ""
    event_info = ""
    
    # Check if it's a URL
    if url_or_file.startswith('http'):
        artist, event_info, setlist = scrape_setlist_from_url(url_or_file)
    else:
        setlist = read_setlist_from_file(url_or_file)
        if setlist and ' - ' in setlist[0]:
            artist = setlist[0].split(' - ')[0]
    
    if not setlist:
        return None
    
    # Generate playlist name if not provided
    if not playlist_name:
        playlist_name = f"{artist} - Concert Setlist" if artist else "Concert Setlist"
    
    # Generate description
    keywords_en = "live concert setlist tour performance rock music playlist"
    keywords_es = "concierto en vivo setlist gira presentación música rock playlist"
    
    description_parts = [
        f"🎸 {artist} Concert Setlist" if artist else "Concert Setlist",
        f"📍 {event_info}" if event_info else "",
        f"🎵 {len(setlist)} songs",
        "",
        f"Keywords: {keywords_en}",
        f"Palabras clave: {keywords_es}",
    ]
    
    description = "\n".join([p for p in description_parts if p])
    
    # Create playlist
    return create_playlist_from_setlist(setlist, playlist_name, description, privacy)

if __name__ == "__main__":
    # Install dependencies if not installed
    try:
        import ytmusicapi
    except ImportError:
        print("📦 Installing ytmusicapi...")
        import subprocess
        subprocess.check_call(["python3", "-m", "pip", "install", "ytmusicapi"])
        import ytmusicapi
    
    # Check for optional dependencies
    try:
        import requests
        import bs4
    except ImportError:
        print("\n💡 For URL scraping, install additional dependencies:")
        print("   pip3 install requests beautifulsoup4")
        print()
    
    main()
