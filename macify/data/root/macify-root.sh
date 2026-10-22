#!/bin/bash
# Ayudante de administrador de Macify. Se ejecuta con pkexec (una sola contraseña).
#   macify-root.sh apply  <carpeta-plymouth> <fondo>
#   macify-root.sh revert
#
# Seguridad: como root sólo se ejecuta código de carpetas de root. WhiteSur se
# descarga aquí mismo, por HTTPS, a /var/cache/macify; de la carpeta del usuario
# sólo se copian datos (las imágenes y el guion del arranque, y el fondo).
set -euo pipefail
umask 022

THEME_DIR=/usr/share/plymouth/themes/macify
THEME_FILE="$THEME_DIR/macify.plymouth"
LINK=/usr/share/plymouth/themes/default.plymouth
CACHE=/var/cache/macify
WHITESUR="$CACHE/WhiteSur-gtk-theme"
REPO=vinceliuice/WhiteSur-gtk-theme
BOOT_FILES="macify.plymouth macify.script logo.png bar-background.png bar-fill.png"

fetch_whitesur() {
  echo "Login screen: downloading WhiteSur as administrator"
  rm -rf "$WHITESUR" "$CACHE/download"
  install -d -m 755 "$CACHE/download"
  curl -fsSL --proto '=https' --tlsv1.2 "https://codeload.github.com/$REPO/tar.gz/refs/heads/master" \
    -o "$CACHE/download/whitesur.tar.gz"
  tar -xzf "$CACHE/download/whitesur.tar.gz" -C "$CACHE/download" --no-same-owner
  mv "$CACHE"/download/WhiteSur-gtk-theme-* "$WHITESUR"
  rm -rf "$CACHE/download"
  chown -R root:root "$WHITESUR"
}

case "${1:-}" in
  apply)
    source_dir="$2"; wallpaper="$3"
    echo "Boot screen: installing the Macify theme"
    install -d -m 755 "$THEME_DIR"
    for name in $BOOT_FILES; do
      install -m 644 "$source_dir/$name" "$THEME_DIR/$name"
    done
    update-alternatives --install "$LINK" default.plymouth "$THEME_FILE" 300
    update-alternatives --set default.plymouth "$THEME_FILE"
    fetch_whitesur
    install -m 644 "$wallpaper" "$CACHE/login-background"
    echo "Login screen: applying the WhiteSur theme"
    (cd "$WHITESUR" && TERM=xterm ./tweaks.sh -g -b "$CACHE/login-background")
    echo "Updating the boot image (initramfs)"
    update-initramfs -u
    ;;
  revert)
    if update-alternatives --query default.plymouth 2>/dev/null | grep -q "$THEME_FILE"; then
      echo "Boot screen: back to the original theme"
      update-alternatives --remove default.plymouth "$THEME_FILE"
    fi
    rm -rf "$THEME_DIR"
    [ -x "$WHITESUR/tweaks.sh" ] || fetch_whitesur
    echo "Login screen: back to the original theme"
    (cd "$WHITESUR" && TERM=xterm ./tweaks.sh -g -r)
    rm -rf "$CACHE"
    echo "Updating the boot image (initramfs)"
    update-initramfs -u
    ;;
  *)
    echo "Usage: $0 apply <plymouth-dir> <wallpaper> | revert" >&2
    exit 2
    ;;
esac
