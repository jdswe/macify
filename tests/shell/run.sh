#!/bin/bash
# Prueba Macify Menubar en un GNOME Shell aislado e invisible (sin cerrar la sesión).
#
# El Shell de prueba tiene su propio bus, sus propios ajustes (una copia de los del
# usuario) y sus propias carpetas de extensiones: nada toca la sesión real. Si el archivo
# de ajustes real cambia durante la prueba, la prueba falla.
#
# Uso: tests/shell/run.sh [carpeta-de-resultados]
#   MACIFY_MONITORS="1920x1080 3840x2160"  pantallas virtuales (por defecto una de 1920x1080)
#   MACIFY_SCALE=2                          escala de todas las pantallas (por defecto 1)
#   MACIFY_TEST_SETTINGS="/ruta/clave=valor;…"  ajustes extra, sólo en la sesión de prueba
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
out=${1:-$(mktemp -d)}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

command -v gnome-shell >/dev/null || { echo "gnome-shell not found"; exit 77; }

extensions="$work/data/gnome-shell/extensions"
mkdir -p "$work/config" "$extensions" "$out"
cp -r "$here/macify-test@macify.dev" "$extensions/"
cp -r "$repo/macify/data/extension/macify-menubar@macify.dev" "$extensions/"
python3 - "$repo" "$extensions/macify-menubar@macify.dev" <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from macify import extensions
icons = Path(sys.argv[2]) / "icons"
icons.mkdir(exist_ok=True)
(icons / "macify-logo-symbolic.svg").write_text(extensions.menubar_logo_svg())
EOF
# Las capturas de pantalla de la prueba van a su propia carpeta, no a las Imágenes reales.
mkdir -p "$work/pictures"
echo "XDG_PICTURES_DIR=\"$work/pictures\"" > "$work/config/user-dirs.dirs"
ln -s "$HOME/.local/share/fonts" "$work/data/fonts"
ln -s "$HOME/.local/share/icons" "$work/data/icons"

dconf dump / > "$work/settings.ini"
python3 - "$work/settings.ini" <<'EOF'
import re, sys
path = sys.argv[1]
text = open(path).read()
text = re.sub(r"(\[org/gnome/shell\]\n(?:.*\n)*?enabled-extensions=\[)", r"\1'macify-test@macify.dev', ", text, count=1)
open(path, "w").write(text)
EOF

# Lo que la prueba cambia en su copia de los ajustes: no debe aparecer en los reales.
guarded() {
    dconf read /org/gnome/shell/enabled-extensions
    dconf read /org/gnome/shell/extensions/dash2dock-lite/autohide-dash
    dconf read /org/gnome/mutter/experimental-features
}
before=$(guarded)
monitors=""
for size in ${MACIFY_MONITORS:-1920x1080}; do
    monitors="$monitors --virtual-monitor $size"
done
env XDG_CONFIG_HOME="$work/config" XDG_DATA_HOME="$work/data" \
    XDG_DATA_DIRS="$HOME/.local/share:/usr/local/share:/usr/share" MACIFY_TEST_OUT="$out" \
    MACIFY_SCALE="${MACIFY_SCALE:-1}" MACIFY_TEST_ONLY="${MACIFY_TEST_ONLY:-}" \
    MACIFY_TEST_SETTINGS="${MACIFY_TEST_SETTINGS:-}" \
    dbus-run-session -- bash -c "
        dconf load / < '$work/settings.ini'
        dconf write /org/gnome/shell/extensions/dash2dock-lite/autohide-dash false
        dconf write /org/gnome/mutter/experimental-features \"['scale-monitor-framebuffer']\"
        IFS=';'; for setting in \$MACIFY_TEST_SETTINGS; do [ -n \"\$setting\" ] && dconf write \"\${setting%%=*}\" \"\${setting#*=}\"; done
        timeout 180 gnome-shell --headless $monitors --wayland" > "$out/shell.log" 2>&1 || true
if [ "$before" != "$(guarded)" ]; then
    echo "ERROR: the test changed the real settings"
    exit 2
fi

grep -h "MACIFY-TEST \(PASS\|FAIL\)" "$out/shell.log" | sed 's/.*MACIFY-TEST //'
grep -A4 "JS ERROR" "$out/shell.log" | head -20 || true
grep -q "MACIFY-TEST DONE" "$out/shell.log" || { echo "ERROR: the test did not finish (see $out/shell.log)"; exit 1; }
! grep -q "MACIFY-TEST FAIL" "$out/shell.log"
