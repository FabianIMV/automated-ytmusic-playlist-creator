# YouTube Music Playlist Creator

Automate the creation of YouTube Music playlists from concert setlists. Perfect for music lovers who attend multiple concerts and want their setlists ready to go.

## What it does

- Reads song lists from a text file
- Automatically searches and adds songs to YouTube Music
- Creates playlists with batch processing
- Handles authentication via browser headers

## Setup

1. **Install dependencies**
```bash
pip install ytmusicapi
```

2. **Get your YouTube Music headers**
   - Go to https://music.youtube.com in Chrome
   - Open DevTools (F12) → Network tab
   - Find any POST request to `browse?key=`
   - Right-click → Copy → Copy as cURL
   - Paste the entire cURL command into `paste.txt`

3. **Create your setlist**
   - Create `setlist.txt` with format:
   ```
   Artist - Song Title
   Oasis - Wonderwall
   Billy Idol - White Wedding
   Morrissey - This Charming Man
   ```

## Usage

```bash
python3 ytmusic_playlist_creator.py
```

The script will:
- Read songs from `setlist.txt`
- Show you a preview
- Ask for playlist name
- Create the playlist automatically

## File Structure

```
ytmusic-playlist-creator/
├── ytmusic_playlist_creator.py  # Main script
├── setlist.txt                  # Your song list (create this)
├── paste.txt                    # cURL headers (create this)
└── headers_auth.json           # Generated automatically
```

## Updating

- **New setlist**: Update `setlist.txt` and run the script
- **Expired headers** (401 error): Update `paste.txt` with fresh cURL

## Example

Input (`setlist.txt`):
```
Oasis - Hello
Oasis - Acquiesce
Billy Idol - Rebel Yell
Morrissey - How Soon Is Now
```

Output: YouTube Music playlist with all found songs

## Notes

- Headers expire periodically - update `paste.txt` when you get 401 errors
- Songs not found in YouTube Music will be skipped
- Works with any artist/song combination