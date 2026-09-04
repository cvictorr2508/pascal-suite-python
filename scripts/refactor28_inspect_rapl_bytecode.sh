#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

EXTRACT_ROOT="${REFACTOR28_EXTRACT_ROOT:-$PROJECT_ROOT/.refactor28-pyi-extracted/pascalanalyzer_extracted}"
PYZ_ROOT="$EXTRACT_ROOT/PYZ-00.pyz_extracted"
RAPL_DIR="$PYZ_ROOT/pascalanalyzer/sensors/rapl"
OUT="$PROJECT_ROOT/refactor28_rapl_bytecode_inspect.txt"
DISASM="$PROJECT_ROOT/refactor28_rapl_bytecode_disassembly.txt"
TARGET_MATCHES="$PROJECT_ROOT/refactor28_rapl_target_matches.txt"
GLOBAL_MATCHES="$PROJECT_ROOT/refactor28_rapl_global_matches.txt"

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
: > "$TARGET_MATCHES"
: > "$GLOBAL_MATCHES"

TERMS='performance_features|profiler|Profiler|perfmon|RAPL_ENERGY|SYSTEMWIDE|region_energy|rapl|package|dram|energy|event'
CORE_TERMS='performance_features|profiler|Profiler|perfmon|RAPL_ENERGY|SYSTEMWIDE|region_energy'

echo "=== TARGET FILES ===" | tee -a "$OUT"
file "$RAPL_PYC" "$RAPL_SAMPLE_PYC" | tee -a "$OUT"
sha256sum "$RAPL_PYC" "$RAPL_SAMPLE_PYC" | tee -a "$OUT"

for path in "$RAPL_PYC" "$RAPL_SAMPLE_PYC"; do
    echo | tee -a "$OUT"
    echo "=== STRINGS: $path ===" | tee -a "$OUT"
    strings -a -n 3 -t d "$path" \
        | grep -Ei "$TERMS" \
        | sed "s#^#$path:#" \
        | tee -a "$OUT" "$TARGET_MATCHES" || true
done

echo | tee -a "$OUT"
echo "=== GLOBAL PYC SEARCH ===" | tee -a "$OUT"
while IFS= read -r -d '' path; do
    strings -a -n 3 -t d "$path" \
        | grep -Ei "$CORE_TERMS" \
        | sed "s#^#$path:#" \
        >> "$GLOBAL_MATCHES" || true
done < <(find "$PYZ_ROOT" -type f -name '*.pyc' -print0)
cat "$GLOBAL_MATCHES" | tee -a "$OUT"

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
    echo "Target-local strings above remain valid; global matches are reported separately." | tee -a "$OUT"
fi

classify_file() {
    local prefix="$1"
    local source="$2"
    local term="$3"
    local label="$4"
    if grep -aEiq "$term" "$source"; then
        echo "${prefix}_${label}=true" | tee -a "$OUT"
    else
        echo "${prefix}_${label}=false" | tee -a "$OUT"
    fi
}

echo | tee -a "$OUT"
echo "=== CLASSIFICATION: RAPL TARGETS ONLY ===" | tee -a "$OUT"
classify_file target_rapl "$TARGET_MATCHES" 'performance_features' performance_features_reference_present
classify_file target_rapl "$TARGET_MATCHES" '(^|[^[:alnum:]_])profiler([^[:alnum:]_]|$)' profiler_reference_present
classify_file target_rapl "$TARGET_MATCHES" '(^|[^[:alnum:]_])Profiler([^[:alnum:]_]|$)' Profiler_reference_present
classify_file target_rapl "$TARGET_MATCHES" 'perfmon' perfmon_reference_present
classify_file target_rapl "$TARGET_MATCHES" 'RAPL_ENERGY' RAPL_ENERGY_reference_present
classify_file target_rapl "$TARGET_MATCHES" 'SYSTEMWIDE' SYSTEMWIDE_reference_present
classify_file target_rapl "$TARGET_MATCHES" 'region_energy' region_energy_reference_present

echo "=== CLASSIFICATION: GLOBAL PYZ ===" | tee -a "$OUT"
classify_file global_pyz "$GLOBAL_MATCHES" 'performance_features' performance_features_reference_present
classify_file global_pyz "$GLOBAL_MATCHES" '(^|[^[:alnum:]_])profiler([^[:alnum:]_]|$)' profiler_reference_present
classify_file global_pyz "$GLOBAL_MATCHES" '(^|[^[:alnum:]_])Profiler([^[:alnum:]_]|$)' Profiler_reference_present
classify_file global_pyz "$GLOBAL_MATCHES" 'perfmon' perfmon_reference_present
classify_file global_pyz "$GLOBAL_MATCHES" 'RAPL_ENERGY' RAPL_ENERGY_reference_present
classify_file global_pyz "$GLOBAL_MATCHES" 'SYSTEMWIDE' SYSTEMWIDE_reference_present
classify_file global_pyz "$GLOBAL_MATCHES" 'region_energy' region_energy_reference_present

echo "target_matches=$TARGET_MATCHES" | tee -a "$OUT"
echo "global_matches=$GLOBAL_MATCHES" | tee -a "$OUT"
echo "report=$OUT" | tee -a "$OUT"
echo "=== RAPL BYTECODE INSPECTION COMPLETED ===" | tee -a "$OUT"
