#!/usr/bin/env python3
"""
YouTube Music Playlist Creator
Automates playlist creation in YouTube Music using ytmusicapi
Supports both txt files and setlist.fm URLs
"""

import json
import os
import re
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
        lines = curl_content.split('\\')  # Split by backslashes
        
        for line in lines:
            line = line.strip()
            
            # Process headers (-H)
            if '-H \'' in line or '-H "' in line:
                # Find header content
                if '-H \'' in line:
                    start = line.find('-H \'') + 4
                    end = line.find('\'', start)
                    if end == -1:
                        header_content = line[start:]
                    else:
                        header_content = line[start:end]
                elif '-H "' in line:
                    start = line.find('-H "') + 4
                    end = line.find('"', start)
                    if end == -1:
                        header_content = line[start:]
                    else:
                        header_content = line[start:end]
                
                # Parse header
                if ':' in header_content:
                    key, value = header_content.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
            
            # Process cookies (-b)
            elif '-b \'' in line or '-b "' in line:
                if '-b \'' in line:
                    start = line.find('-b \'') + 4
                    end = line.find('\'', start)
                    if end == -1:
                        cookie_content = line[start:]
                    else:
                        cookie_content = line[start:end]
                elif '-b "' in line:
                    start = line.find('-b "') + 4
                    end = line.find('"', start)
                    if end == -1:
                        cookie_content = line[start:]
                    else:
                        cookie_content = line[start:end]
                
                headers['cookie'] = cookie_content
        
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

def create_playlist_from_setlist(setlist, playlist_name, description="", privacy="PUBLIC"):
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
        
        # Create playlist
        print(f"🎵 Creating playlist: {playlist_name}")
        print(f"🔓 Privacy: {privacy}")
        playlist_id = ytmusic.create_playlist(
            playlist_name, 
            description,
            privacy_status=privacy
        )
        print(f"✅ Playlist created with ID: {playlist_id}")
        
        successful_adds = 0
        failed_songs = []
        
        # Search and add each song
        for i, song in enumerate(setlist, 1):
            print(f"🔍 [{i}/{len(setlist)}] Searching: {song}")
            
            try:
                # Search for the song
                search_results = ytmusic.search(song, filter="songs", limit=5)
                
                if search_results:
                    # Use first result
                    video_id = search_results[0]['videoId']
                    song_title = search_results[0].get('title', 'Unknown')
                    artist = search_results[0].get('artists', [{}])[0].get('name', 'Unknown')
                    
                    # Add to playlist
                    ytmusic.add_playlist_items(playlist_id, [video_id])
                    print(f"  ✅ Added: {artist} - {song_title}")
                    successful_adds += 1
                else:
                    print(f"  ❌ Not found: {song}")
                    failed_songs.append(song)
                    
            except Exception as e:
                print(f"  ❌ Error with '{song}': {str(e)}")
                failed_songs.append(song)
        
        # Summary
        print(f"\n🎉 Playlist '{playlist_name}' created successfully!")
        print(f"✅ Songs added: {successful_adds}/{len(setlist)}")
        
        if failed_songs:
            print(f"❌ Songs not found:")
            for song in failed_songs:
                print(f"   - {song}")
        
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
    """Main function - interactive mode"""
    
    print("🎸 YouTube Music Playlist Creator")
    print("=" * 50)
    print("1. Create from setlist.fm URL")
    print("2. Create from txt file")
    print("=" * 50)
    
    choice = input("\nChoose option [1/2]: ").strip()
    
    setlist = []
    artist = ""
    event_info = ""
    
    if choice == "1":
        # URL mode
        url = input("\n🔗 Enter setlist.fm URL: ").strip()
        if not url:
            print("❌ URL required")
            return
        
        artist, event_info, setlist = scrape_setlist_from_url(url)
        if not setlist:
            return
            
    elif choice == "2":
        # File mode
        filename = input("\n📁 Enter filename [setlist.txt]: ").strip()
        if not filename:
            filename = "setlist.txt"
        
        setlist = read_setlist_from_file(filename)
        if not setlist:
            return
        
        # Extract artist from first song if possible
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
    
    custom_desc = input("Custom description (leave empty to use default): ").strip()
    description = custom_desc if custom_desc else default_description
    
    # Privacy setting
    print("\n🔒 Privacy options:")
    print("1. PUBLIC (anyone can find and view)")
    print("2. UNLISTED (only people with link can view)")
    print("3. PRIVATE (only you can view)")
    
    privacy_choice = input("Choose privacy [1/2/3]: ").strip()
    privacy_map = {"1": "PUBLIC", "2": "UNLISTED", "3": "PRIVATE"}
    privacy = privacy_map.get(privacy_choice, "PUBLIC")
    
    # Confirm before creating
    print(f"\n📝 Summary:")
    print(f"   Name: {playlist_name}")
    print(f"   Songs: {len(setlist)}")
    print(f"   Privacy: {privacy}")
    print()
    
    confirm = input(f"Create playlist? [y/N]: ").strip().lower()
    if confirm not in ['y', 'yes', 's', 'si', 'sí']:
        print("❌ Operation cancelled")
        return
    
    # Create playlist
    playlist_id = create_playlist_from_setlist(
        setlist, 
        playlist_name, 
        description,
        privacy
    )
    
    if playlist_id:
        print(f"\n🔗 Playlist URL: https://music.youtube.com/playlist?list={playlist_id}")
        print(f"\n💡 To create another playlist, run the script again!")

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
