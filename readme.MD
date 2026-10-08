<div align="center">

<img src="frontend/public/favicon.svg" width="72" alt="" />

# Playlist Creator

**Convierte el setlist de un concierto en una playlist de YouTube Music en un par de clics.**

Pega la lista de canciones o un enlace de setlist.fm, revisa el resultado y listo: la playlist aparece en tu cuenta.

[![Abrir la app](https://img.shields.io/badge/Abrir_la_app-ytmusic--playlist--creator-e11d48?style=for-the-badge&logo=render&logoColor=white)](https://ytmusic-playlist-creator-9bub.onrender.com)

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.14x-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Tailwind](https://img.shields.io/badge/Tailwind-4-06B6D4?logo=tailwindcss&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-Auth-3FCF8E?logo=supabase&logoColor=white)
![CI](https://github.com/FabianIMV/automated-ytmusic-playlist-creator/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/licencia-MIT-green.svg)

<br />

<img src="docs/screenshots/07-terminada.webp" alt="Playlist creada: 20 de 21 canciones agregadas, con botón para abrirla en YouTube Music" width="900" />

</div>

---

## ✨ Qué hace

| | |
|---|---|
| 🎤 **Desde cualquier setlist** | Pega una lista (`Artista - Canción`, una por línea) o un enlace de [setlist.fm](https://www.setlist.fm). |
| 👀 **Revisas antes de crear** | Vista previa editable: quita canciones, cambia el nombre, la descripción y la privacidad. |
| 🔍 **Busca cada canción** | Encuentra la versión en YouTube Music, evita duplicados y te dice cuáles no encontró. |
| ⚡ **Progreso en vivo** | Ves canción por canción cómo se busca y se agrega, con miniaturas. |
| 🔁 **Reintentos y playlists existentes** | Reintenta las que faltaron o suma canciones a una playlist que ya tienes. |
| 🔐 **Entra con Google** | Un clic para iniciar sesión y conectar tu YouTube, sin copiar nada. |
| 🧩 **API + Postman + CLI** | Todo lo que hace la UI también se puede hacer por API o desde la terminal. |

## 📸 Así se usa

### 1. Entra con tu cuenta de Google

<img src="docs/screenshots/01-login.webp" alt="Pantalla de inicio de sesión con el botón Continuar con Google" width="900" />

### 2. Conecta YouTube (modo simple, sin copiar nada)

Al entrar con Google autorizas a la app a crear playlists en tu cuenta. Si prefieres, puedes elegir explícitamente el **modo avanzado (cURL)**, útil para listas muy grandes.

<table>
<tr>
<td width="50%"><img src="docs/screenshots/02-conectar-google.webp" alt="Modal Conectar YouTube Music en modo simple con el botón Conectar con Google" /></td>
<td width="50%"><img src="docs/screenshots/03-modo-avanzado.webp" alt="Modal en modo avanzado con los pasos para copiar el cURL" /></td>
</tr>
<tr>
<td align="center"><sub>Modo simple (predeterminado)</sub></td>
<td align="center"><sub>Modo avanzado (cURL), solo si lo eliges</sub></td>
</tr>
</table>

### 3. Pega el setlist y revisa la vista previa

<img src="docs/screenshots/04-pegar-setlist.webp" alt="Lista de canciones pegada con el contador de 21 canciones" width="900" />

<img src="docs/screenshots/05-vista-previa.webp" alt="Vista previa con las canciones, nombre, descripción y privacidad de la playlist" width="900" />

### 4. Mira cómo se arma en vivo

<img src="docs/screenshots/06-progreso.webp" alt="Job en curso: 8 de 21 canciones encontradas con barra de progreso" width="900" />

### 5. ¡Lista! Ábrela en YouTube Music

<img src="docs/screenshots/08-detalle-canciones.webp" alt="Detalle de canciones con miniatura, artista y estado de cada una" width="900" />

Y todo queda en tu historial:

<img src="docs/screenshots/09-historial.webp" alt="Historial con la playlist creada y sus contadores" width="900" />

### 📱 También en el celular

<p align="center">
<img src="docs/screenshots/10-movil-inicio.webp" alt="Pantalla de inicio en el celular" width="300" />
&nbsp;&nbsp;&nbsp;
<img src="docs/screenshots/11-movil-progreso.webp" alt="Progreso de una búsqueda de prueba en el celular" width="300" />
</p>

<sub>Capturas tomadas con Playwright sobre la app real, con YouTube Music simulado.</sub>

## 🧠 Cómo funciona

```
 UI (React)  ·  Postman / curl  ·  CLI
        │              │             │
        └──── API FastAPI ───────────┤   auth (Supabase) · jobs en background
                       │             │
                Núcleo playlist_creator.core
          setlist → búsqueda → playlist en lotes
                       │
        ┌──────────────┴───────────────┐
  Modo simple                    Modo avanzado
  YouTube Data API (Google)      ytmusicapi (cURL del navegador)
```

| Modo | Cómo se conecta | Límite |
|---|---|---|
| **Simple** (predeterminado) | Botón «Conectar con Google» | ~200 canciones por día (cuota gratuita de YouTube) |
| **Avanzado** | Pegas un cURL de music.youtube.com | Sin cuota; ideal para listas grandes |

Las credenciales se guardan **cifradas** en Supabase y nunca vuelven al navegador. Más detalle en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## 🚀 Úsalo

**En la nube:** [ytmusic-playlist-creator-9bub.onrender.com](https://ytmusic-playlist-creator-9bub.onrender.com). La primera carga puede tardar unos segundos si el servidor estaba dormido.

**En tu computador:**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn playlist_creator.api.main:app --reload      # API en http://localhost:8000 (docs en /docs)

cd frontend && npm install && npm run dev            # UI en http://localhost:5173
```

O simplemente `./run.sh`.

**Por API** (importa [`postman/`](postman/ytmusic-playlist-creator.postman_collection.json) en Postman):

```bash
curl -X POST "http://localhost:8000/api/playlists?wait=true" \
  -H "Content-Type: application/json" \
  -d '{"source": {"type": "songs", "songs": ["Oasis - Wonderwall", "Blur - Song 2"]}, "privacy": "PRIVATE"}'
```

**Desde la terminal:**

```bash
python3 ytmusic_playlist_creator.py -f setlist.txt -n "Mi playlist" -p PRIVATE
python3 ytmusic_playlist_creator.py -u "https://www.setlist.fm/setlist/..." --dry-run
```

## 📚 Documentación

- [Guía completa](README_ES.md): instalación, conexión, variables de entorno y deploy paso a paso en Render + Supabase.
- [Arquitectura y contrato de la API](docs/ARQUITECTURA.md).
- Swagger en `/docs` de la API.

## 🛠️ Stack

**Backend:** Python 3.13, FastAPI, ytmusicapi, YouTube Data API v3, Pydantic · **Frontend:** React 19, Vite, TypeScript, Tailwind CSS 4, lucide · **Infra:** Render (Docker), Supabase (Auth + Postgres), GitHub Actions.

---

<div align="center">
<sub>Hecho con 🎸 para no volver a armar playlists de conciertos a mano. Esta app no está afiliada a YouTube ni a Google.</sub>
</div>
