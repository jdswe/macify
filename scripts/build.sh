#!/usr/bin/env bash
# Empaqueta Macify en un único archivo ejecutable: dist/macify.pyz
# Uso: ./scripts/build.sh   (desde la carpeta app/)
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$APP_DIR/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$DIST"
cp -r "$APP_DIR/macify" "$STAGE/macify"
find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} +

# Punto de entrada del archivo: ejecuta el paquete macify.
cat > "$STAGE/__main__.py" <<'PY'
import sys

from macify.__main__ import main

sys.exit(main())
PY

python3 -m zipapp "$STAGE" -o "$DIST/macify.pyz" -p "/usr/bin/env python3"
chmod +x "$DIST/macify.pyz"
echo "Listo: $DIST/macify.pyz"
