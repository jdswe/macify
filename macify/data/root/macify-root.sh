#!/bin/bash
# Ayudante de administrador de Macify. Se ejecuta con pkexec (una sola contraseña).
#   macify-root.sh apply  <carpeta-plymouth> <fondo>
#   macify-root.sh revert
#
# Seguridad:
# - Como root sólo se ejecuta código de carpetas de root: WhiteSur se descarga aquí mismo,
#   en una versión fija, y se comprueba su huella SHA-256 antes de usarlo.
# - Lo que llega de la carpeta de la persona (imágenes y guion del arranque, fondo) se lee
#   con SUS permisos, no los de root: así nadie puede hacer que root copie un archivo que
#   ella no puede leer (por ejemplo, /etc/shadow). Sólo archivos normales, de los tipos y
#   tamaños esperados.
set -euo pipefail
umask 022

THEME_DIR=/usr/share/plymouth/themes/macify
THEME_FILE="$THEME_DIR/macify.plymouth"
LINK=/usr/share/plymouth/themes/default.plymouth
CACHE=/var/cache/macify
WHITESUR="$CACHE/WhiteSur-gtk-theme"
REPO=vinceliuice/WhiteSur-gtk-theme
WHITESUR_COMMIT=d5782652d412137e26fb8ff55b55a5572e4c6995
WHITESUR_SHA256=9d8be3dca76f7be36dfb6513aa2c301be1ff265a9c1c4c1006b5ed0f89df29f1
BOOT_IMAGES="logo.png bar-background.png bar-fill.png"
BOOT_TEXTS="macify.plymouth macify.script"
MAX_BOOT_FILE=$((4 * 1024 * 1024))
MAX_WALLPAPER=$((64 * 1024 * 1024))

die() {
  echo "Error: $*" >&2
  exit 1
}

# Lee un archivo con los permisos de quien pidió la contraseña (pkexec o sudo).
read_as_user() {
  local uid="${PKEXEC_UID:-${SUDO_UID:-0}}"
  if [ "$uid" = 0 ]; then
    cat -- "$1"
  else
    setpriv --reuid="$uid" --regid="$(id -g "$uid")" --init-groups -- cat -- "$1"
  fi
}

# Copia un archivo de la persona a una carpeta de root, comprobando tipo y tamaño.
take() {
  local source="$1" target="$2" kind="$3" limit="$4"
  [ -f "$source" ] && [ ! -L "$source" ] || die "not a regular file: $source"
  [ "$(stat -c %s -- "$source")" -le "$limit" ] || die "file too large: $source"
  set +o pipefail
  read_as_user "$source" | head -c "$((limit + 1))" > "$target"
  local status=${PIPESTATUS[0]}
  set -o pipefail
  [ "$status" = 0 ] || [ "$status" = 141 ] || die "cannot read (with your permissions): $source"
  [ -s "$target" ] && [ "$(stat -c %s "$target")" -le "$limit" ] || die "empty or too large: $source"
  local magic
  magic=$(head -c 4 "$target" | od -An -tx1 | tr -d ' \n')
  case "$kind" in
    png) [ "$magic" = 89504e47 ] || die "not a PNG image: $source" ;;
    image) [[ "$magic" = 89504e47 || "$magic" = ffd8ff* ]] || die "not a JPEG or PNG image: $source" ;;
    text) [ "$(tr -d '\000' < "$target" | wc -c)" = "$(stat -c %s "$target")" ] || die "not a text file: $source" ;;
  esac
}

fetch_whitesur() {
  echo "Login screen: downloading WhiteSur ${WHITESUR_COMMIT:0:7} as administrator"
  rm -rf "$WHITESUR" "$CACHE/download"
  install -d -m 755 "$CACHE/download"
  curl -fsSL --proto '=https' --tlsv1.2 "https://codeload.github.com/$REPO/tar.gz/$WHITESUR_COMMIT" \
    -o "$CACHE/download/whitesur.tar.gz"
  echo "$WHITESUR_SHA256  $CACHE/download/whitesur.tar.gz" | sha256sum --check --status \
    || die "WhiteSur download does not match its fingerprint; nothing was run"
  tar -xzf "$CACHE/download/whitesur.tar.gz" -C "$CACHE/download" --no-same-owner
  mv "$CACHE"/download/WhiteSur-gtk-theme-* "$WHITESUR"
  rm -rf "$CACHE/download"
  echo "$WHITESUR_COMMIT" > "$WHITESUR/.macify-commit"
  chown -R root:root "$WHITESUR"
}

# La copia en caché sólo vale si es exactamente la versión fijada.
whitesur_ready() {
  [ -x "$WHITESUR/tweaks.sh" ] && [ "$(cat "$WHITESUR/.macify-commit" 2>/dev/null)" = "$WHITESUR_COMMIT" ]
}

main() {
  case "${1:-}" in
    apply)
      [ $# -eq 3 ] || die "usage: $0 apply <plymouth-dir> <wallpaper>"
      source_dir="$2"; wallpaper="$3"
      staging=$(mktemp -d /run/macify.XXXXXX)
      trap 'rm -rf "$staging"' EXIT
      for name in $BOOT_IMAGES; do take "$source_dir/$name" "$staging/$name" png "$MAX_BOOT_FILE"; done
      for name in $BOOT_TEXTS; do take "$source_dir/$name" "$staging/$name" text "$MAX_BOOT_FILE"; done
      take "$wallpaper" "$staging/login-background" image "$MAX_WALLPAPER"

      echo "Boot screen: installing the Macify theme"
      install -d -m 755 "$THEME_DIR"
      for name in $BOOT_IMAGES $BOOT_TEXTS; do
        install -m 644 "$staging/$name" "$THEME_DIR/$name"
      done
      update-alternatives --install "$LINK" default.plymouth "$THEME_FILE" 300
      update-alternatives --set default.plymouth "$THEME_FILE"
      fetch_whitesur
      install -m 644 "$staging/login-background" "$CACHE/login-background"
      echo "Login screen: applying the WhiteSur theme"
      (cd "$WHITESUR" && TERM=xterm ./tweaks.sh -g -b "$CACHE/login-background")
      echo "Updating the boot image (initramfs)"
      update-initramfs -u
      ;;
    revert)
      [ $# -eq 1 ] || die "usage: $0 revert"
      if update-alternatives --query default.plymouth 2>/dev/null | grep -q "$THEME_FILE"; then
        echo "Boot screen: back to the original theme"
        update-alternatives --remove default.plymouth "$THEME_FILE"
      fi
      rm -rf "$THEME_DIR"
      whitesur_ready || fetch_whitesur
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
}

# Al cargarlo desde las pruebas sólo se definen las funciones.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
