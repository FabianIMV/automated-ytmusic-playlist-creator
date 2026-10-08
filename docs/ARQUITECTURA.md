# Propuesta de arquitectura v2

El script original (`ytmusic_playlist_creator.py`) mezclaba lectura de setlists, autenticación,
búsqueda, creación de la playlist y prompts de consola en un solo archivo. La v2 separa eso en un
**núcleo reutilizable** que consumen tres "caras":

```
                ┌──────────────┐   ┌───────────────┐   ┌──────────────┐
                │  UI (React)  │   │ Postman / curl│   │     CLI      │
                └──────┬───────┘   └──────┬────────┘   └──────┬───────┘
                       │  HTTP + JSON     │                   │ import
                       ▼                  ▼                   │
                ┌─────────────────────────────────┐           │
                │  API FastAPI  (playlist_creator │           │
                │  .api)  auth · jobs · rutas      │           │
                └──────────────┬──────────────────┘           │
                               ▼                              ▼
                ┌──────────────────────────────────────────────────┐
                │ Núcleo (playlist_creator.core)                   │
                │  sources ─ credentials ─ music (MusicClient) ─   │
                │  builder (run_job con progreso)                  │
                └──────────────────────┬───────────────────────────┘
                                       ▼
                          YouTube Music (ytmusicapi)
```

## Estructura

```
playlist_creator/
  models.py            Modelos Pydantic compartidos (fuentes, Track, Job, PlaylistRequest)
  config.py            Settings por variables de entorno / .env
  core/
    sources.py         Texto, lista o setlist.fm  → Setlist (+ nombre/descripción sugeridos)
    credentials.py     Parseo de cURL/headers + CredentialStore (archivo por usuario)
    music.py           MusicClient (interfaz) + YTMusicClient (ytmusicapi)
    builder.py         prepare_job / run_job: busca, deduplica, crea y agrega en lotes
  api/
    main.py            create_app(): CORS, rutas, sirve frontend/dist si existe
    auth.py            AUTH_MODE=none | supabase (verificación de JWT)
    jobs.py            JobManager: jobs en memoria + ThreadPoolExecutor
    routes/account.py  /api/health, /api/me, /api/ytmusic/credentials
    routes/playlists.py /api/setlists/parse, /api/search, /api/playlists, /api/jobs
frontend/              Vite + React + TypeScript + Tailwind (UI)
tests/                 pytest (núcleo + API con un MusicClient falso)
ytmusic_playlist_creator.py   CLI (mismos flags que antes, ahora usa el núcleo)
```

## Contrato de la API

Base: `http://localhost:8000`. Documentación interactiva en `/docs` (Swagger) y `/redoc`.
Con `AUTH_MODE=supabase` todas las rutas salvo `/api/health` exigen `Authorization: Bearer <access_token de Supabase>`.
Errores: `{"detail": "mensaje"}` (o la lista de errores de validación de FastAPI en 422).

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | `{status, version, auth_mode}` |
| GET | `/api/me` | `{user:{id,email,name,avatar_url}, auth_mode, ytmusic: YTMusicStatus}` |
| GET | `/api/ytmusic/credentials` | `YTMusicStatus` = `{connected, account:{name,handle,photo_url}\|null, error}` |
| PUT | `/api/ytmusic/credentials` | Body `{raw: "<cURL o headers>"}`. Valida contra YouTube Music y guarda. 422 si no sirven |
| DELETE | `/api/ytmusic/credentials` | 204 |
| POST | `/api/setlists/parse` | Body `Source`. Devuelve `Setlist` (no toca YouTube Music) |
| GET | `/api/search?q=...` | `{query, track: Track\|null}` |
| POST | `/api/playlists[?wait=true]` | Body `PlaylistRequest`. 202 + `Job` (o 200 + `Job` terminado con `wait=true`). 409 si no hay credenciales y no es `dry_run` |
| GET | `/api/jobs` | `Job[]` sin `items`, más recientes primero |
| GET | `/api/jobs/{id}` | `Job` completo (para hacer polling ~1 s) |

### Tipos

```jsonc
// Source (discriminado por "type")
{"type": "text", "text": "Oasis - Wonderwall\nBlur - Song 2"}   // una por línea, ignora vacías y "#"
{"type": "songs", "songs": ["Oasis - Wonderwall", "Blur - Song 2"]}
{"type": "setlistfm", "url": "https://www.setlist.fm/setlist/..."}

// Setlist
{"artist": "Oasis", "event_info": "Estadio Nacional - Nov 2025", "songs": ["..."],
 "suggested_name": "Oasis - Concert Setlist", "suggested_description": "🎸 ..."}

// PlaylistRequest
{
  "source": Source,
  "name": "opcional (default: suggested_name)",
  "description": "opcional (default: suggested_description)",
  "privacy": "PUBLIC | UNLISTED | PRIVATE",          // default PUBLIC
  "playlist_id": "opcional: ID o URL de playlist existente → agrega ahí",
  "dry_run": false                                     // true: solo busca, no escribe
}

// Track
{"video_id": "...", "title": "...", "artists": ["..."], "album": "...|null",
 "duration": "3:45|null", "thumbnail": "https://...|null", "result_type": "song|video"}

// Job
{
  "id": "hex", "owner_id": "local|<uuid supabase>",
  "status": "queued | running | completed | failed",
  "created_at": "...", "started_at": "...|null", "finished_at": "...|null",
  "dry_run": false, "name": "...", "description": "...", "privacy": "PUBLIC",
  "artist": "...|null", "event_info": "...|null",
  "playlist_id": "...|null", "playlist_url": "https://music.youtube.com/playlist?list=...|null",
  "summary": {"total": 20, "processed": 12, "found": 10, "added": 0, "duplicates": 1, "not_found": 1, "errors": 0},
  "items": [{"index": 0, "query": "Oasis - Wonderwall",
             "status": "pending | found | duplicate | not_found | error",
             "track": Track|null, "error": "...|null"}],
  "message": null, "error": "...|null"
}
```

Notas:
- `summary.added` sube después de cada lote (por defecto 50 canciones, 3 s de pausa entre lotes).
- "Reintentar no encontradas" = nuevo `POST /api/playlists` con las `query` de items `not_found`/`error`
  y `playlist_id` del job anterior.
- Las búsquedas usan las credenciales del usuario si existen: sin sesión YouTube Music tiende a
  devolver videos/covers en vez de canciones (sobre todo desde IPs de servidores).

## Autenticación (lista para Supabase + Google)

1. **Modo local** (`AUTH_MODE=none`, por defecto): sin login; todo pertenece al usuario `local`.
   Si existe el `headers_auth.json` de la CLI, se importa automáticamente al arrancar.
2. **Modo Supabase** (`AUTH_MODE=supabase`):
   - En Supabase: Authentication → Providers → **Google** (client ID/secret de Google Cloud) y agregar la
     URL del frontend en *Redirect URLs*.
   - Frontend: `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` → botón "Continuar con Google"
     (`supabase.auth.signInWithOAuth({provider: "google"})`) y envía el `access_token` como Bearer.
   - Backend: `SUPABASE_URL` (+ `SUPABASE_JWT_SECRET` solo si el proyecto usa el secreto HS256 legacy;
     si no, valida con las llaves públicas JWKS del proyecto).
   - Postman: copiar el token desde la UI (menú de usuario → "Copiar token de API").

La sesión de Google identifica **quién** eres. Para **escribir** en YouTube Music se siguen usando los
headers del navegador (pegados una vez por usuario desde la UI). Alternativa futura: pedir el scope
`https://www.googleapis.com/auth/youtube` en el login de Google y usar la YouTube Data API v3 con ese
token (oficial, sin copiar cookies), implementando otro `MusicClient`. Contra: cuota de 10.000
unidades/día y cada canción agregada cuesta 50 (~200 canciones/día) salvo que Google amplíe la cuota.

## Deploy ("que viva solito")

Recomendado: **un solo contenedor** (API + frontend compilado) en un PaaS que despliega desde GitHub,
con **Supabase** para login y para persistir las credenciales:

| Pieza | Opción recomendada | Alternativas |
|---|---|---|
| API + UI | Render (Docker, `render.yaml`, plan free: se duerme tras 15 min sin uso) | Fly.io (auto-stop/start, pago por uso), Railway (~5 USD/mes), Koyeb |
| Login | Supabase Auth + Google | — |
| Credenciales YT | Supabase (`CREDENTIAL_STORE=supabase`, cifradas con Fernet) | archivo en un volumen persistente |
| Solo frontend | mismo contenedor | GitHub Pages / Cloudflare Pages / Vercel (+ `VITE_API_BASE_URL` y `CORS_ORIGINS`) |

Cuidado con:
- Los jobs viven en memoria: si la instancia se reinicia a mitad de un job, se pierde el progreso
  (la playlist queda con lo agregado hasta ese momento). La UI hace polling, así que mantiene la
  instancia despierta mientras corre un job. Si hiciera falta, `JobManager` se puede respaldar en una tabla.
- Las cookies de YouTube Music son credenciales completas de tu cuenta de Google: en un deploy
  multiusuario guárdalas solo cifradas y nunca las expongas al frontend.
- Google puede invalidar la sesión si detecta uso desde IPs muy distintas; si pasa, la UI pide
  volver a pegar el cURL (el estado `ytmusic.connected=false` trae el motivo en `error`).

## Próximos pasos posibles

- `MusicClient` con YouTube Data API v3 (token de Google vía Supabase) para eliminar el paso del cURL.
- Persistir jobs en Supabase (historial entre reinicios y entre dispositivos).
- Editar manualmente la coincidencia de una canción antes de crear la playlist (`/api/search`).
