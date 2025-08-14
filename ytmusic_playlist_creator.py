#!/usr/bin/env python3
"""
YouTube Music Playlist Creator
Automates playlist creation in YouTube Music using ytmusicapi
"""

import json
import os
from ytmusicapi import YTMusic

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

def create_playlist_from_setlist(setlist, playlist_name, description=""):
    """
    Create a YouTube Music playlist from a list of songs
    
    Args:
        setlist (list): List of strings with format "Artist - Song"
        playlist_name (str): Name of the playlist
        description (str): Optional description
    """
    try:
        # Initialize YouTube Music
        ytmusic = setup_ytmusic()
        
        if not ytmusic:
            return None
        
        # Create playlist
        print(f"🎵 Creating playlist: {playlist_name}")
        playlist_id = ytmusic.create_playlist(playlist_name, description)
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
    """Main function - reads setlist from file"""
    
    # Read setlist from file
    setlist = read_setlist_from_file("setlist.txt")
    
    if not setlist:
        return
    
    # Show setlist preview
    print(f"\n📋 Setlist preview:")
    for i, song in enumerate(setlist[:5], 1):
        print(f"   {i}. {song}")
    if len(setlist) > 5:
        print(f"   ... and {len(setlist) - 5} more songs")
    
    # Playlist configuration
    playlist_name = input(f"\n🎵 Playlist name [Concert Playlist]: ").strip()
    if not playlist_name:
        playlist_name = "Concert Playlist"
    
    description = f"Setlist with {len(setlist)} songs imported from setlist.txt"
    
    # Confirm before creating
    confirm = input(f"\n¿Create playlist '{playlist_name}' with {len(setlist)} songs? [y/N]: ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Operation cancelled")
        return
    
    # Create playlist
    playlist_id = create_playlist_from_setlist(
        setlist, 
        playlist_name, 
        description
    )
    
    if playlist_id:
        print(f"\n🔗 Playlist URL: https://music.youtube.com/playlist?list={playlist_id}")
        print(f"\n💡 To use again:")
        print(f"   1. Update setlist.txt with new songs")
        print(f"   2. Run: python3 ytmusic_playlist_creator.py")

if __name__ == "__main__":
    # Install ytmusicapi if not installed
    try:
        import ytmusicapi
    except ImportError:
        print("Installing ytmusicapi...")
        import subprocess
        subprocess.check_call(["python3", "-m", "pip", "install", "ytmusicapi"])
        import ytmusicapi
    
    main()
