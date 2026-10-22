#!/bin/bash
# Hace el video de presentación de Macify (1080p, con música original):
#   1. pantallas de la app (capture.py), con el fondo original «Lilac»
#   2. pantallas de GNOME en una sesión de prueba aislada (tests/shell, modo demo)
#   3. la web (Firefox sin ventana)
#   4. render.py dibuja cada cuadro y music.py compone el audio
# Uso: scripts/demo/make_video.sh [salida.mp4]   (por defecto docs/demo.mp4)
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
out=${1:-$repo/docs/demo.mp4}
work=$(mktemp -d)
web=$(mktemp -d -p "$HOME" macify-web.XXXXXX)       # Firefox (snap) no escribe en /tmp ni en carpetas ocultas
trap 'rm -rf "$work" "$web"' EXIT
wallpaper="file://$repo/macify/data/wallpapers/lilac.jpg"

echo "1/4 app screens"
PYTHONPATH="$repo" python3 -c "from macify import boot; boot.build_theme()"
for try in 1 2; do
    timeout 120 python3 -u "$here/capture.py" "$work/app" > "$work/capture.log" 2>&1 && break
    echo "   app capture timed out, retrying"
done
[ -f "$work/app/13-doctor.png" ] || { echo "app capture failed:"; tail -5 "$work/capture.log"; exit 1; }

echo "2/4 GNOME screens (hidden test session)"
MACIFY_TEST_ONLY=demo \
MACIFY_TEST_SETTINGS="/org/gnome/desktop/background/picture-uri='$wallpaper';/org/gnome/desktop/background/picture-uri-dark='$wallpaper'" \
    "$repo/tests/shell/run.sh" "$work/shell" > /dev/null 2>&1 || true
for shot in desktop menu-edit menu-window menu-battery menu-wifi menu-sound control-center osd date-menu \
    screenshot-preview now-playing app-grid badge; do
    [ -f "$work/shell/$shot.png" ] || { echo "missing GNOME screen: $shot"; exit 1; }
done

echo "3/4 website"
mkdir -p "$web/profile"
timeout 90 firefox --headless --no-remote --profile "$web/profile" --window-size=1440,5600 \
    --screenshot "$web/web.png" "https://jdswe.github.io/macify/" > /dev/null 2>&1
mv "$web/web.png" "$work/web.png"

echo "4/4 rendering"
python3 "$here/render.py" "$work" "$out"
