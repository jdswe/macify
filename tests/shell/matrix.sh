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
# MACIFY_MATRIX_JOBS=2 corre varias a la vez: más rápido, pero comparten /run/user y con
# carga alta alguna puede fallar por tiempos; la verificación final va de una en una.
jobs=${MACIFY_MATRIX_JOBS:-1}
results=$(mktemp -d)
one() {
    local index=$1 layout=$2
    local monitors=${layout%|*} scale=${layout#*|} out
    out=$(mktemp -d)
    if MACIFY_MONITORS="$monitors" MACIFY_SCALE="$scale" "$here/run.sh" "$out" > "$out/summary.txt" 2>&1; then
        echo "PASS  [$monitors] scale $scale  ($(grep -c '^PASS' "$out/summary.txt") checks)" > "$results/$index"
    else
        { echo "FAIL  [$monitors] scale $scale  — see $out"
          grep -E '^FAIL|ERROR' "$out/summary.txt" | sed 's/^/      /'; } > "$results/$index"
    fi
}
for index in "${!layouts[@]}"; do
    one "$index" "${layouts[$index]}" &
    while [ "$(jobs -rp | wc -l)" -ge "$jobs" ]; do wait -n; done
done
wait
failed=0
for index in "${!layouts[@]}"; do
    cat "$results/$index"
    grep -q '^FAIL' "$results/$index" && failed=1
done
rm -rf "$results"
exit $failed
