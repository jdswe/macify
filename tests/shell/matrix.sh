#!/bin/bash
# Corre las pruebas del Shell con distintas pantallas y escalas:
# una pantalla, dos, tres, y escalas 1, 1.25, 1.5 y 2.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
layouts=(
    "1920x1080|1"
    "1366x768|1"
    "3840x2160|2"
    "1920x1080 3840x2160|1"
    "1920x1080 2560x1440|1.25"
    "2560x1600|1.5"
    "1920x1080 1920x1080 1280x1024|1"
)
failed=0
for layout in "${layouts[@]}"; do
    monitors=${layout%|*}
    scale=${layout#*|}
    out=$(mktemp -d)
    if MACIFY_MONITORS="$monitors" MACIFY_SCALE="$scale" "$here/run.sh" "$out" > "$out/summary.txt" 2>&1; then
        echo "PASS  [$monitors] scale $scale  ($(grep -c '^PASS' "$out/summary.txt") checks)"
    else
        echo "FAIL  [$monitors] scale $scale  — see $out"
        grep -E '^FAIL|ERROR' "$out/summary.txt" | sed 's/^/      /'
        failed=1
    fi
done
exit $failed
