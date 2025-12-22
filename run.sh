#!/bin/bash
# Script auxiliar para ejecutar el creador de playlists

echo "🎸 YouTube Music Playlist Creator"
echo "=================================="
echo ""
echo "⚠️  IMPORTANTE: Primero necesitas configurar la autenticación"
echo ""
echo "📝 Pasos para obtener las credenciales:"
echo "1. Abre Chrome y ve a https://music.youtube.com"
echo "2. Inicia sesión si no lo has hecho"
echo "3. Presiona F12 para abrir DevTools"
echo "4. Ve a la pestaña 'Network' (Red)"
echo "5. Busca en la página (reproduce una canción o navega)"
echo "6. Busca una petición POST que contenga 'browse?key='"
echo "7. Click derecho en la petición → Copy → Copy as cURL"
echo "8. Pega TODO el comando en un archivo llamado 'paste.txt'"
echo ""
echo "Cuando tengas paste.txt listo, presiona ENTER para continuar..."
read -p ""

# Activar entorno virtual
source venv/bin/activate

# Ejecutar el script
python3 ytmusic_playlist_creator.py
