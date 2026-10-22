#!/usr/bin/env bash
# Instala la última versión de Macify desde los releases oficiales de GitHub.
#   curl -fsSL https://jdswe.github.io/macify/install.sh | bash
# Verifica la huella SHA-256 publicada por GitHub y que el paquete sea «macify».
set -euo pipefail

REPO="jdswe/macify"
api="https://api.github.com/repos/$REPO/releases/latest"

command -v apt-get >/dev/null || { echo "Macify needs Ubuntu (apt)."; exit 1; }

release="$(curl -fsSL "$api")"
read -r url digest < <(python3 -c '
import json, sys
release = json.load(sys.stdin)
asset = next(a for a in release["assets"] if a["name"].endswith("_all.deb"))
print(asset["browser_download_url"], (asset.get("digest") or "none").removeprefix("sha256:"))
' <<<"$release")

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
chmod 755 "$tmp"
echo "Downloading $url"
curl -fsSL --proto '=https' "$url" -o "$tmp/macify.deb"

if [ "$digest" != "none" ]; then
  echo "$digest  $tmp/macify.deb" | sha256sum -c --quiet || { echo "Fingerprint mismatch: not installing."; exit 1; }
fi
[ "$(dpkg-deb -f "$tmp/macify.deb" Package)" = "macify" ] || { echo "Not the Macify package: not installing."; exit 1; }

chmod 644 "$tmp/macify.deb"
sudo apt-get install -y "$tmp/macify.deb"
# Si Macify ya estaba aplicado, la versión nueva aplica sólo lo que cambió y borra lo viejo
# (sin reinstalar todo). El detalle queda en ~/.cache/macify/upgrade.log.
if [ -f "$HOME/.config/macify/config.json" ]; then
  echo
  echo "Applying only what changed…"
  mkdir -p "$HOME/.cache/macify"
  /usr/bin/macify upgrade > "$HOME/.cache/macify/upgrade.log" 2>&1 || true
  grep -E "^(Updating|Cleaned|Actualizando|Se liberaron)" "$HOME/.cache/macify/upgrade.log" || true
  echo
  echo "Macify is updated. Log out and back in to see everything new."
else
  echo
  echo "Macify is installed. Open it from your apps."
fi
