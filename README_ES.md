# 🎸 YouTube Music Playlist Creator

Automatiza la creación de playlists en YouTube Music a partir de setlists de conciertos. Pega una lista de canciones, sube un archivo de texto o indica una URL de setlist.fm: la app busca cada canción y crea la playlist por ti.

> **Versión 2:** interfaz web, API REST con colección de Postman y la CLI original, todo sobre el mismo núcleo.

## ✨ Qué hace

- 🌐 **Lee setlists** desde texto, desde una lista de canciones o desde una URL de [setlist.fm](https://www.setlist.fm/).
- 🔍 **Busca cada canción** en YouTube Music y muestra al final las que no encontró.
- 📦 **Procesa por lotes** (50 canciones por lote, con pausa entre lotes) para no saturar la cuenta.
- 🔓 **Elige la privacidad:** `PUBLIC`, `UNLISTED` o `PRIVATE`.
- ➕ **Agrega a una playlist existente** si ya la tienes.
- 🔐 **Inicio de sesión con Google** (opcional, con Supabase) para desplegarla y usarla con más personas.

## 🖼️ Capturas

*Próximamente:* las capturas de la interfaz irán en `docs/screenshot.png`.

## 🚀 Inicio rápido (local)

Requisitos: **Python 3.13** (la versión que usan el contenedor y la CI) y **Node.js 22** (solo para la interfaz web).

1. Crea el entorno virtual e instala las dependencias de Python:

   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Levanta la API:

   ```bash
   uvicorn playlist_creator.api.main:app --reload
   ```

   La API queda en http://localhost:8000 y su documentación en http://localhost:8000/docs.

3. En otra terminal, levanta la interfaz web:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Abre **http://localhost:5173**.

También puedes ejecutar `./run.sh`. Crea `.venv` si no existe, instala las dependencias y levanta la API. Si ya hiciste `npm install` dentro de `frontend/`, levanta también la interfaz. Con Ctrl+C se detienen ambos procesos.

## 🎵 Conecta tu cuenta de YouTube Music

La app usa las cabeceras de tu sesión del navegador para escribir en tu cuenta. Solo tienes que copiarlas una vez, y repetir el proceso cuando caduquen:

1. Abre https://music.youtube.com en Chrome e inicia sesión.
2. Presiona **F12** y ve a la pestaña **Network** (Red).
3. Reproduce una canción o navega por la página.
4. Busca una petición **POST** cuya URL contenga `browse?key=`.
5. Haz clic derecho sobre ella y elige **Copy → Copy as cURL (bash)**.
6. Pega el cURL completo en la sección de conexión con YouTube Music de la interfaz.

La app valida el cURL contra YouTube Music antes de guardarlo. También acepta las cabeceras en texto plano (*Copy request headers*). Si la conexión caduca, la interfaz te lo indica y puedes volver a pegarlo.

> ⚠️ Esas cabeceras dan acceso completo a tu cuenta de Google. No las compartas ni las subas al repositorio.

## 🧪 Uso desde la API y Postman

Importa `postman/ytmusic-playlist-creator.postman_collection.json` en Postman. La variable `baseUrl` apunta a `http://localhost:8000`. En modo local deja `token` vacío.

Para crear una playlist y esperar el resultado con `curl`:

```bash
curl -X POST "http://localhost:8000/api/playlists?wait=true" \
  -H "Content-Type: application/json" \
  -d '{
        "source": {"type": "songs", "songs": ["Oasis - Wonderwall", "Blur - Song 2"]},
        "name": "Britpop",
        "privacy": "PRIVATE"
      }'
```

- `source.type` puede ser `text` (una canción por línea; ignora líneas vacías y las que empiezan con `#`), `songs` (lista) o `setlistfm` (URL).
- Con `"dry_run": true` solo busca las canciones y no escribe nada en YouTube Music.
- Con `"playlist_id"` agrega las canciones a una playlist existente (acepta el ID o la URL).
- Sin `?wait=true`, la API responde `202` con un job. Consúltalo en `GET /api/jobs/{id}`.
- Si usas `AUTH_MODE=supabase`, añade `-H "Authorization: Bearer <access_token>"`.

El contrato completo (tipos, estados y errores) está en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) y en `/docs`.

## 💻 CLI (sigue funcionando)

La CLI original usa el mismo núcleo que la API. Lee las cabeceras de `paste.txt` (el cURL del paso de conexión) y genera `headers_auth.json`.

```bash
python3 ytmusic_playlist_creator.py -f setlist.txt
python3 ytmusic_playlist_creator.py -u "https://www.setlist.fm/setlist/..."
python3 ytmusic_playlist_creator.py -f setlist.txt -n "Mi playlist" -p PRIVATE
python3 ytmusic_playlist_creator.py -f setlist.txt --playlist-id PLxxxxxxxx
python3 ytmusic_playlist_creator.py -f setlist.txt --dry-run   # solo busca, no escribe
```

| Opción | Descripción |
|---|---|
| `-f`, `--file` | Archivo de texto con una canción por línea (`Artista - Canción`) |
| `-u`, `--url` | URL de un setlist de setlist.fm |
| `-n`, `--name` | Nombre de la playlist |
| `-d`, `--description` | Descripción de la playlist |
| `-p`, `--privacy` | `PUBLIC` (por defecto), `UNLISTED` o `PRIVATE` |
| `--playlist-id` | Agrega a una playlist existente (ID o URL) en vez de crear una nueva |
| `--dry-run` | Solo busca las canciones; no crea ni modifica playlists |
| `-a`, `--auto` | Modo no interactivo: no hace preguntas y usa los valores por defecto |

## 🚢 Despliegue en Render + Supabase

La arquitectura de producción es un **solo contenedor** (API + frontend compilado) en [Render](https://render.com), con [Supabase](https://supabase.com) para el inicio de sesión con Google y para guardar las credenciales cifradas. Las decisiones de diseño están en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

### 1. Crear el proyecto en Supabase

1. Crea un proyecto en https://supabase.com.
2. Ejecuta `supabase/migrations/20261008000000_ytmusic_credentials.sql` en el **SQL Editor** del proyecto (o `supabase db push` con la CLI de Supabase). Crea la tabla de credenciales con RLS activado y sin políticas: solo el backend puede leerla.
3. Anota estos valores desde la configuración de API del proyecto:
   - **Project URL** (`https://xxxx.supabase.co`): para `SUPABASE_URL` y para `VITE_SUPABASE_URL`.
   - **anon key** (pública): para `VITE_SUPABASE_ANON_KEY`.
   - **service_role / secret key** (secreta, solo para el backend): para `SUPABASE_SERVICE_KEY`.
   - Si el proyecto todavía usa el **JWT secret legacy** (HS256), cópialo en `SUPABASE_JWT_SECRET`. Con las llaves de firma nuevas (JWT Signing Keys) no hace falta: la API valida los tokens con las llaves públicas (JWKS) del proyecto.

### 2. Activar Google como proveedor

1. Ve a **Authentication → Providers → Google** y actívalo.
2. Pega el **Client ID** y el **Client Secret** de un cliente OAuth creado en Google Cloud Console. En Google Cloud, usa como URI de redirección el que muestra Supabase en esa misma pantalla.

### 3. Generar la clave de cifrado

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Guarda el resultado: será el valor de `CREDENTIALS_ENCRYPTION_KEY`. Si lo pierdes, las credenciales ya guardadas no se pueden descifrar y hay que volver a pegar el cURL.

### 4. Crear el Blueprint en Render

1. En Render, elige **New → Blueprint** y conecta este repositorio. Render leerá `render.yaml`.
2. Render te pedirá los valores de las variables sin valor fijo:

   | Variable | Valor |
   |---|---|
   | `SUPABASE_URL` | Project URL del paso 1 |
   | `SUPABASE_SERVICE_KEY` | service_role / secret key del paso 1 |
   | `CREDENTIALS_ENCRYPTION_KEY` | La clave Fernet del paso 3 |
   | `CORS_ORIGINS` | Vacío si usas solo Render. Si usas GitHub Pages, `https://<tu-usuario>.github.io` |
   | `VITE_SUPABASE_URL` | El mismo valor que `SUPABASE_URL` |
   | `VITE_SUPABASE_ANON_KEY` | La anon key del paso 1 |

   Las variables `VITE_*` llegan al `docker build` como build args, porque el Dockerfile las declara con `ARG`. Si las cambias, vuelve a desplegar para recompilar el frontend.

3. Espera a que termine el despliegue. Render comprueba `/api/health` antes de dar el servicio por listo. Anota la URL del servicio (por ejemplo, `https://ytmusic-playlist-creator.onrender.com`).

### 5. Agregar la URL del deploy en Supabase

1. En Supabase, ve a **Authentication → URL Configuration → Redirect URLs**.
2. Agrega la URL de Render. Si además pruebas con Supabase en tu equipo, agrega también `http://localhost:5173`.

### 6. Probar

Abre la URL de Render, inicia sesión con Google y conecta tu cuenta de YouTube Music con el cURL, igual que en local.

### Notas del plan gratuito

- El servicio **se duerme** tras 15 minutos sin uso. La primera carga después de un rato tarda en responder.
- Los jobs viven en memoria. Si el servicio se reinicia a mitad de un job, se pierde el progreso, aunque lo ya agregado queda en la playlist. Mientras corre un job, la interfaz consulta su estado, lo que ayuda a mantener el servicio despierto.
- El disco es efímero. Por eso las credenciales se guardan en Supabase (`CREDENTIAL_STORE=supabase`) y no en disco.
- Nunca pongas `SUPABASE_SERVICE_KEY` ni `CREDENTIALS_ENCRYPTION_KEY` en el frontend ni en el repositorio.

## 🌐 Alternativa: frontend en GitHub Pages

También puedes publicar solo el frontend en GitHub Pages y dejar la API en Render. El workflow `pages.yml` es manual a propósito: solo se ejecuta con **Run workflow**, así no falla si Pages todavía no está activado.

1. En GitHub, ve a **Settings → Pages** y elige **Source: GitHub Actions**.
2. Ve a **Settings → Secrets and variables → Actions** y, en la pestaña **Variables**, crea:
   - `API_BASE_URL`: URL de tu API en Render.
   - `SUPABASE_URL`: Project URL de Supabase.
   - `SUPABASE_ANON_KEY`: anon key de Supabase.
3. En Render, define `CORS_ORIGINS=https://<tu-usuario>.github.io` (solo el origen, sin la ruta del repositorio) y espera al redespliegue.
4. En Supabase, agrega la URL de Pages a **Redirect URLs**.
5. Ve a **Actions → Deploy frontend a GitHub Pages → Run workflow**.

La interfaz quedará en `https://<tu-usuario>.github.io/<repositorio>/`. La ruta base se configura sola con el nombre del repositorio.

## ⚙️ Variables de entorno principales

La lista completa, comentada, está en [`.env.example`](.env.example).

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `AUTH_MODE` | `none` | `none` = sin login (uso local); `supabase` = exige un JWT de Supabase |
| `CREDENTIAL_STORE` | `file` | Dónde se guardan las credenciales: `file` (disco) o `supabase` (cifradas) |
| `DATA_DIR` | `data` | Carpeta de credenciales por usuario cuando `CREDENTIAL_STORE=file` |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Orígenes permitidos, separados por comas |
| `FRONTEND_DIST` | `frontend/dist` | Frontend compilado que sirve la API, si existe |
| `BATCH_SIZE` | `50` | Canciones por lote |
| `BATCH_DELAY_SECONDS` | `3` | Pausa entre lotes, en segundos |
| `JOB_WORKERS` | `2` | Jobs que se ejecutan en paralelo |
| `MAX_SONGS_PER_JOB` | `1000` | Máximo de canciones por job |
| `YTMUSIC_LANGUAGE` | `en` | Idioma de las respuestas de YouTube Music |

## 🛠️ Solución de problemas

- **422 al guardar el cURL:** copia el comando completo. Debe incluir las cabeceras `authorization` y `cookie`.
- **YouTube Music rechazó las credenciales:** las cabeceras caducaron. Vuelve a copiarlas desde el navegador.
- **409 al crear una playlist:** conecta primero tu cuenta de YouTube Music, o usa `"dry_run": true` para solo buscar.
- **401 "Falta el token" (con `AUTH_MODE=supabase`):** inicia sesión en la interfaz, o pon un token válido en la variable `token` de Postman.
- **422 "Máximo N canciones por playlist":** la fuente trae más canciones que `MAX_SONGS_PER_JOB`.
- **Una canción no aparece:** revisa el nombre del artista y de la canción, y prueba variantes (por ejemplo, "MCR" en vez de "My Chemical Romance"). Sin sesión de YouTube Music, las búsquedas tienden a devolver videos o covers, sobre todo desde servidores.

## 📚 Documentación

- [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md): arquitectura, contrato de la API y estrategia de deploy.
- `/docs` en la API (Swagger) y `/redoc`.

## 📄 Licencia

MIT. Úsalo como quieras.
