![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Stars](https://img.shields.io/github/stars/FabianIMV/automated-ytmusic-playlist-creator)

# YouTube Music Playlist Creator

Turn concert setlists into YouTube Music playlists. Paste a song list, a text file, or a setlist.fm URL, and the app searches every song and builds the playlist for you.

Version 2 offers three ways to use it: a web UI, a REST API (with a Postman collection), and the original CLI.

## Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn playlist_creator.api.main:app --reload     # API on http://localhost:8000

# In another terminal, for the web UI:
cd frontend && npm install && npm run dev          # UI on http://localhost:5173
```

Then connect your YouTube Music account from the UI by pasting the cURL copied from your browser's DevTools.

## Usage

- **Web UI:** http://localhost:5173
- **API docs:** http://localhost:8000/docs
- **Postman:** import `postman/ytmusic-playlist-creator.postman_collection.json`
- **CLI:** `python3 ytmusic_playlist_creator.py -f setlist.txt`

## Deploy

The app runs as a single container (API + built frontend) on Render, with Supabase for Google login and encrypted credentials. See [README_ES.md](README_ES.md) for the step-by-step guide (in Spanish) and [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) for the architecture and deploy strategy.

## Notes

- YouTube Music headers expire periodically. Reconnect the account from the UI when you get an authentication error.
- Songs that are not found are reported at the end instead of failing the whole playlist.
- Your cookies are full access to your Google account: keep `.env`, `data/` and `headers_auth.json` private.

## License

MIT
