#!/usr/bin/env bash
# Genera el paquete instalable dist/macify_<version>_all.deb
# Uso: ./scripts/build_deb.sh   (desde la carpeta app/)
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="0.4.2"
PKG="macify_${VERSION}_all"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
ROOT="$STAGE/$PKG"

# Código Python en /usr/lib/macify
install -d "$ROOT/usr/lib/macify"
cp -r "$APP_DIR/macify" "$ROOT/usr/lib/macify/"
find "$ROOT" -name "__pycache__" -type d -prune -exec rm -rf {} +

# Comando de terminal y acceso en el menú de aplicaciones
install -d "$ROOT/usr/bin" "$ROOT/usr/share/applications" "$ROOT/usr/share/icons/hicolor/scalable/apps"
install -m 644 "$APP_DIR/macify/data/dev.macify.Macify.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/"
cat > "$ROOT/usr/bin/macify" <<'SH'
#!/bin/sh
PYTHONPATH=/usr/lib/macify exec /usr/bin/python3 -m macify "$@"
SH
chmod 755 "$ROOT/usr/bin/macify"
cat > "$ROOT/usr/share/applications/dev.macify.Macify.desktop" <<'DESK'
[Desktop Entry]
Name=Macify
Comment=Convierte Ubuntu en un Mac con un clic
Exec=macify
Icon=dev.macify.Macify
Terminal=false
Type=Application
Categories=Settings;DesktopSettings;
StartupWMClass=dev.macify.Macify
DESK

# Metadatos del paquete: las dependencias las instala apt automáticamente
install -d "$ROOT/DEBIAN"
cat > "$ROOT/DEBIAN/control" <<CTRL
Package: macify
Version: ${VERSION}
Section: gnome
Priority: optional
Architecture: all
Maintainer: jdswe <jdswe@users.noreply.github.com>
Homepage: https://github.com/jdswe/macify
Depends: python3, python3-gi, python3-pil, 7zip | p7zip-full, gir1.2-gtk-4.0, gir1.2-adw-1, pkexec | policykit-1, libglib2.0-bin, fontconfig, sassc, libxml2-utils, libglib2.0-dev-bin
Description: Configura Ubuntu con estilo macOS
 Asistente que convierte el escritorio GNOME de Ubuntu al estilo macOS:
 ventanas, iconos, cursor, fuentes San Francisco, dock animado, barra
 superior de cristal, fondo y colores. Guarda copia de seguridad y se
 puede restaurar o desinstalar sin dejar rastro.
CTRL

install -d "$APP_DIR/dist"
dpkg-deb --build --root-owner-group "$ROOT" "$APP_DIR/dist/${PKG}.deb"
echo "Listo: $APP_DIR/dist/${PKG}.deb"
