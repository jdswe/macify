#!/bin/bash
# Ayudante de administrador de Macify. Se ejecuta con pkexec (una sola contraseña).
#   macify-root.sh apply  <carpeta-plymouth> <carpeta-whitesur> <fondo>
#   macify-root.sh revert <carpeta-whitesur>
# Las pantallas de arranque y de inicio de sesión son del sistema: por eso necesitan root.
set -euo pipefail

THEME_DIR=/usr/share/plymouth/themes/macify
THEME_FILE="$THEME_DIR/macify.plymouth"
LINK=/usr/share/plymouth/themes/default.plymouth

case "${1:-}" in
  apply)
    source_dir="$2"; whitesur="$3"; wallpaper="$4"
    echo "Boot screen: installing the Macify theme"
    install -d "$THEME_DIR"
    install -m 644 "$source_dir"/* "$THEME_DIR"/
    update-alternatives --install "$LINK" default.plymouth "$THEME_FILE" 300
    update-alternatives --set default.plymouth "$THEME_FILE"
    if [ -x "$whitesur/tweaks.sh" ]; then
      echo "Login screen: applying the WhiteSur theme"
      (cd "$whitesur" && TERM=xterm ./tweaks.sh -g -b "$wallpaper")
    fi
    echo "Updating the boot image (initramfs)"
    update-initramfs -u
    ;;
  revert)
    whitesur="${2:-}"
    if update-alternatives --query default.plymouth 2>/dev/null | grep -q "$THEME_FILE"; then
      echo "Boot screen: back to the original theme"
      update-alternatives --remove default.plymouth "$THEME_FILE"
    fi
    rm -rf "$THEME_DIR"
    if [ -n "$whitesur" ] && [ -x "$whitesur/tweaks.sh" ]; then
      echo "Login screen: back to the original theme"
      (cd "$whitesur" && TERM=xterm ./tweaks.sh -g -r)
    fi
    echo "Updating the boot image (initramfs)"
    update-initramfs -u
    ;;
  *)
    echo "Usage: $0 apply <plymouth-dir> <whitesur-dir> <wallpaper> | revert <whitesur-dir>" >&2
    exit 2
    ;;
esac
