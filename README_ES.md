# 🎸 YouTube Music Playlist Creator

Automatiza la creación de playlists en YouTube Music a partir de setlists de conciertos.

## ✨ Características

- 🌐 **Scraping desde setlist.fm** - Extrae canciones directamente desde URLs
- 📁 **Archivos de texto** - Soporta archivos .txt con formato "Artista - Canción"
- 🔓 **Playlists públicas** - Configura privacidad (Público/No listado/Privado)
- 🌍 **Descripciones bilingües** - Keywords en inglés y español para mejor búsqueda
- 🎯 **Búsqueda inteligente** - Encuentra automáticamente las canciones en YouTube Music

## 🚀 Instalación

1. **Instalar dependencias:**
```bash
pip3 install ytmusicapi requests beautifulsoup4
```

2. **Configurar autenticación de YouTube Music:**
   - Ve a https://music.youtube.com en Chrome
   - Abre DevTools (F12) → Pestaña Network
   - Busca cualquier petición POST a 'browse?key='
   - Click derecho → Copy → Copy as cURL
   - Pega todo el comando cURL en un archivo llamado `paste.txt`
   - Ejecuta el script

## 💡 Uso

### Modo Interactivo
```bash
python3 ytmusic_playlist_creator.py
```

El script te preguntará:
1. ¿Quieres usar una URL o un archivo txt?
2. Nombre de la playlist
3. Descripción (opcional)
4. Privacidad (Público/No listado/Privado)

### Ejemplos de URLs de setlist.fm

Para My Chemical Romance:
```
https://www.setlist.fm/setlist/my-chemical-romance/2025/piedmont-park-atlanta-ga-4b5bcbe6.html
https://www.setlist.fm/setlist/my-chemical-romance/2025/raymond-james-stadium-tampa-fl-2b5e8852.html
```

Para The Hives:
```
https://www.setlist.fm/setlist/the-hives/2024/[buscar-en-setlist-fm].html
```

### Formato de archivo txt

Si prefieres usar un archivo .txt, el formato es:
```
Artista - Canción
My Chemical Romance - Welcome to the Black Parade
My Chemical Romance - I'm Not Okay (I Promise)
The Hives - Hate to Say I Told You So
```

## 🎯 Ejemplo de Uso para Conciertos

### My Chemical Romance
1. Busca el setlist en https://www.setlist.fm/
2. Copia la URL del concierto
3. Ejecuta el script y pega la URL
4. Nombra la playlist: "My Chemical Romance - Tampa 2025"
5. Selecciona "PUBLIC" para que otros fans la encuentren

### The Hives
1. Repite el mismo proceso
2. Nombra la playlist: "The Hives - Concert Setlist"
3. Selecciona "PUBLIC"

## 🔒 Opciones de Privacidad

- **PUBLIC**: Cualquiera puede encontrar y ver la playlist (ideal para compartir)
- **UNLISTED**: Solo personas con el link pueden verla
- **PRIVATE**: Solo tú puedes verla

## 📝 Keywords Automáticas

El script agrega automáticamente keywords en inglés y español:
- **EN**: live concert setlist tour performance rock music playlist
- **ES**: concierto en vivo setlist gira presentación música rock playlist

Esto ayuda a que la gente encuentre tus playlists cuando busque contenido de conciertos.

## 🎵 Notas

- El script busca automáticamente cada canción en YouTube Music
- Si una canción no se encuentra, te mostrará cuáles fallaron
- Las playlists públicas aparecen en búsquedas de YouTube Music
- Puedes ejecutar el script múltiples veces para crear varias playlists

## 🛠️ Solución de Problemas

### "No valid headers found"
- Asegúrate de copiar el cURL completo en `paste.txt`
- El comando debe incluir cookies y headers de autorización

### "Missing dependencies for URL scraping"
```bash
pip3 install requests beautifulsoup4
```

### Una canción no se encuentra
- Verifica el nombre del artista y la canción
- Prueba con variaciones del nombre (ej: "MCR" vs "My Chemical Romance")

## 📄 Licencia

MIT License - Úsalo como quieras!
