# 🎸 Guía Rápida - Crear Playlists de My Chemical Romance y The Hives

## 📋 Paso 1: Configurar Autenticación (SOLO UNA VEZ)

1. **Abre Chrome** y ve a: https://music.youtube.com
2. **Inicia sesión** en tu cuenta de YouTube
3. **Presiona F12** (o botón derecho → Inspeccionar)
4. **Ve a la pestaña "Network"** (o "Red")
5. **Reproduce cualquier canción** o navega en la página
6. **Busca una petición** que diga "browse" (usa Ctrl+F en la lista)
   - Debe ser tipo POST
   - La URL debe contener `browse?key=`
7. **Click derecho** en esa petición → Copy → **Copy as cURL (bash)**
8. **Pega TODO** el contenido en un archivo llamado `paste.txt` (en esta carpeta)

El comando debe verse algo así:
```
curl 'https://music.youtube.com/youtubei/v1/browse?key=...' \
  -H 'authorization: SAPISIDHASH ...' \
  -H 'cookie: VISITOR_INFO1_LIVE=...; ...' \
  ...
```

## 🚀 Paso 2: Ejecutar el Script

### Opción A: Usar URLs de setlist.fm (RECOMENDADO)

```bash
./run.sh
```

Luego:
1. Selecciona opción **1** (Create from setlist.fm URL)
2. Pega la URL del setlist:
   - MCR Tampa: https://www.setlist.fm/setlist/my-chemical-romance/2025/raymond-james-stadium-tampa-fl-2b5e8852.html
   - MCR Atlanta: https://www.setlist.fm/setlist/my-chemical-romance/2025/piedmont-park-atlanta-ga-4b5bcbe6.html
3. Elige nombre (ej: "My Chemical Romance - Tampa 2025 🖤")
4. Selecciona privacidad: **1** (PUBLIC)
5. Confirma con **y**

### Opción B: Usar archivos .txt

```bash
./run.sh
```

Luego:
1. Selecciona opción **2** (Create from txt file)
2. Escribe: `mcr_setlist.txt` o `the_hives_setlist.txt`
3. Elige nombre (ej: "MCR Concert Setlist 🎸")
4. Selecciona privacidad: **1** (PUBLIC)
5. Confirma con **y**

## 📱 Ejemplos de Nombres Creativos

### My Chemical Romance:
- "My Chemical Romance - Tampa 2025 🖤"
- "MCR Live Setlist 🎸 Welcome to the Black Parade"
- "My Chemical Romance Concert Playlist 🔥"

### The Hives:
- "The Hives - Live Energy ⚡"
- "The Hives Concert Setlist 🎸"
- "Hate to Say I Told You So - The Hives Live"

## ✅ Qué Esperar

El script:
- ✅ Creará la playlist en tu cuenta
- ✅ Buscará automáticamente cada canción
- ✅ Agregará las que encuentre
- ✅ Te mostrará cuáles no pudo encontrar
- ✅ Te dará el link de la playlist al final

## 🔧 Solución de Problemas

### Error: "No valid headers found"
- Asegúrate de copiar **TODO** el comando cURL
- Debe incluir `-H 'authorization: ...'` y `-H 'cookie: ...'`
- Guárdalo en un archivo llamado exactamente `paste.txt`

### Error: "Missing dependencies"
Ya están instaladas en el `venv`, solo asegúrate de usar `./run.sh`

### Una canción no se encuentra
Es normal, algunas canciones pueden tener nombres diferentes en YouTube Music.
El script te mostrará cuáles no encontró al final.

## 🎵 URLs de Setlist.fm para Buscar

- My Chemical Romance: https://www.setlist.fm/setlists/my-chemical-romance-bd68c0e.html
- The Hives: https://www.setlist.fm/setlists/the-hives-6bd68eba.html

Busca el concierto más reciente y copia la URL completa.

## 💡 Tips Pro

1. **Nombres descriptivos**: Incluye fecha y lugar
2. **Emojis**: Hacen que la playlist se vea mejor
3. **PUBLIC**: Para que otros fans la encuentren
4. **Keywords**: El script agrega automáticamente keywords en inglés y español

¡Disfruta tus playlists! 🎸🖤
