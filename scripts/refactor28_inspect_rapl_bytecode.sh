#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

EXTRACT_ROOT="${REFACTOR28_EXTRACT_ROOT:-$PROJECT_ROOT/.refactor28-pyi-extracted/pascalanalyzer_extracted}"
PYZ_ROOT="$EXTRACT_ROOT/PYZ-00.pyz_extracted"
RAPL_DIR="$PYZ_ROOT/pascalanalyzer/sensors/rapl"
OUT="$PROJECT_ROOT/refactor28_rapl_bytecode_inspect.txt"
DISASM="$PROJECT_ROOT/refactor28_rapl_bytecode_disassembly.txt"

RAPL_PYC="$RAPL_DIR/rapl.pyc"
RAPL_SAMPLE_PYC="$RAPL_DIR/rapl_sample.pyc"

for path in "$RAPL_PYC" "$RAPL_SAMPLE_PYC"; do
    if [[ ! -f "$path" ]]; then
        echo "missing_extracted_pyc=$path" >&2
        echo "Run scripts/refactor28_inspect_pyinstaller_archive.sh first." >&2
        exit 2
    fi
done

: > "$OUT"
: > "$DISASM"

TERMS='performance_features|profiler|Profiler|perfmon|RAPL_ENERGY|SYSTEMWIDE|region_energy|package|dram|energy|event'

echo "=== TARGET FILES ===" | tee -a "$OUT"
file "$RAPL_PYC" "$RAPL_SAMPLE_PYC" | tee -a "$OUT"
sha256sum "$RAPL_PYC" "$RAPL_SAMPLE_PYC" | tee -a "$OUT"

for path in "$RAPL_PYC" "$RAPL_SAMPLE_PYC"; do
    echo | tee -a "$OUT"
    echo "=== STRINGS: $path ===" | tee -a "$OUT"
    strings -a -n 3 -t d "$path" | grep -Ei "$TERMS" | tee -a "$OUT" || true

done

echo | tee -a "$OUT"
echo "=== GLOBAL PYC SEARCH ===" | tee -a "$OUT"
find "$PYZ_ROOT" -type f -name '*.pyc' -print0 \
    | xargs -0 grep -aHnEi 'performance_features|profiler|Profiler|perfmon|RAPL_ENERGY|SYSTEMWIDE|region_energy' \
    | tee -a "$OUT" || true

echo | tee -a "$OUT"
echo "=== OPTIONAL PYTHON 3.8 DISASSEMBLY ===" | tee -a "$OUT"
PY38=""
for candidate in python3.8 python3.8m; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PY38="$(command -v "$candidate")"
        break
    fi
done

if [[ -n "$PY38" ]]; then
    echo "python38=$PY38" | tee -a "$OUT"
    "$PY38" - "$RAPL_PYC" "$RAPL_SAMPLE_PYC" > "$DISASM" <<'PY'
import dis
import marshal
import pathlib
import sys

for raw in sys.argv[1:]:
    path = pathlib.Path(raw)
    print(f"=== {path} ===")
    with path.open("rb") as stream:
        header = stream.read(16)
        print("pyc_header_hex=", header.hex())
        code = marshal.load(stream)
    print("co_names=", code.co_names)
    print("co_consts=", code.co_consts)
    print("--- disassembly ---")
    dis.dis(code)
    print()
PY
    grep -nEi "$TERMS" "$DISASM" | tee -a "$OUT" || true
    echo "disassembly=$DISASM" | tee -a "$OUT"
else
    echo "python38_available=false" | tee -a "$OUT"
    echo "String/name inspection above remains valid; no runtime package was installed." | tee -a "$OUT"
fi

echo | tee -a "$OUT"
echo "=== CLASSIFICATION ===" | tee -a "$OUT"
for term in performance_features profiler Profiler perfmon RAPL_ENERGY SYSTEMWIDE region_energy; do
    if grep -aEiq "$term" "$OUT"; then
        echo "${term}_reference_present=true" | tee -a "$OUT"
    else
        echo "${term}_reference_present=false" | tee -a "$OUT"
    fi
done

echo "report=$OUT" | tee -a "$OUT"
echo "=== RAPL BYTECODE INSPECTION COMPLETED ===" | tee -a "$OUT"
