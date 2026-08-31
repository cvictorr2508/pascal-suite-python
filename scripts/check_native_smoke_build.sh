#!/bin/bash
set -Eeuo pipefail

PASCAL_ROOT="${PASCAL_ROOT:-/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08}"
BUILD_DIR="${BUILD_DIR:-.refactor26-build}"
BIN="$BUILD_DIR/smoke_pascal_region_native"

mkdir -p "$BUILD_DIR"

gcc \
    -O2 \
    -std=c11 \
    -I"$PASCAL_ROOT/include" \
    scripts/smoke_pascal_region_native.c \
    -L"$PASCAL_ROOT/lib" \
    -Wl,-rpath,"$PASCAL_ROOT/lib" \
    -lmpascalops \
    -o "$BIN"

printf 'Built: %s\n' "$BIN"
ldd "$BIN" | grep -E 'mpascalops|not found' || true
