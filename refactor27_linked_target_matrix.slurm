#!/bin/bash
#SBATCH --job-name=pascal_target27
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:10:00
#SBATCH --exclusive
#SBATCH --output=target27_%j.out
#SBATCH --error=target27_%j.err
#SBATCH --partition=intel-256

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true

set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"

PASCAL_ROOT="/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08"
PASCAL_LIB="$PASCAL_ROOT/lib/libmpascalops.so"
PYTHON_BIN="$(command -v python3)"
DIAG_SCRIPT="$SLURM_SUBMIT_DIR/scripts/diagnose_pascal_loader.py"
BUILD_DIR="$SLURM_SUBMIT_DIR/.refactor27-build"
LAUNCHER="$BUILD_DIR/pascal_linked_launcher"
STRINGS_FILE="$BUILD_DIR/libmpascalops_strings.txt"

mkdir -p "$BUILD_DIR"
rm -f "$LAUNCHER" "$STRINGS_FILE"

printf '%s\n' "=== HOST ==="
hostname

printf '%s\n' "=== TOOLCHAIN ==="
command -v gcc
gcc --version | sed -n '1p'

printf '%s\n' "=== ANALYZER ==="
ANALYZER="$(command -v pascalanalyzer)"
printf 'analyzer=%s\n' "$ANALYZER"
readlink -f "$ANALYZER" || true
file "$ANALYZER" || true
sed -n '1,3p' "$ANALYZER" 2>/dev/null || true

printf '%s\n' "=== BUILD LINKED LAUNCHER ==="
gcc \
    -O2 \
    -std=c11 \
    -I"$PASCAL_ROOT/include" \
    "$SLURM_SUBMIT_DIR/scripts/pascal_linked_launcher.c" \
    -L"$PASCAL_ROOT/lib" \
    -Wl,-rpath,"$PASCAL_ROOT/lib" \
    -lmpascalops \
    -o "$LAUNCHER"

printf '%s\n' "=== LAUNCHER ELF NEEDED ==="
readelf -d "$LAUNCHER" | grep NEEDED || true

printf '%s\n' "=== LAUNCHER LINKAGE ==="
ldd "$LAUNCHER" | grep -E 'mpascalops|not found' || true

printf '%s\n' "=== LIBMPASCALOPS RELEVANT IMPORTS ==="
readelf -Ws "$PASCAL_LIB" \
  | grep UND \
  | grep -Ei 'getenv|shm|socket|fifo|pipe|open|read|write|pthread|omp|fork|exec' \
  || true

printf '%s\n' "=== LIBMPASCALOPS RELEVANT STRINGS ==="
strings "$PASCAL_LIB" \
  | grep -Ei 'pascal|region|running|shm|socket|fifo|pipe|/tmp|thread' \
  > "$STRINGS_FILE" || true
sed -n '1,160p' "$STRINGS_FILE"

summarize_json() {
    local json="$1"
    python3 - "$json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
print(f"json={path}")
if not path.exists():
    print("json_exists=false")
    raise SystemExit(0)

payload = json.loads(path.read_text(encoding="utf-8"))
print("json_exists=true")
for run_key, run in (payload.get("data") or {}).items():
    regions = run.get("regions") if isinstance(run, dict) else None
    print(f"run={run_key} regions={regions}")
PY
}

run_launcher_case() {
    local name="$1"
    local launcher_mode="$2"
    local json="$SLURM_SUBMIT_DIR/refactor27_target_${name}.json"

    printf '\n%s\n' "=================================================="
    printf 'CASE=%s\n' "$name"
    printf 'PASCAL_LAUNCHER_MODE=%s\n' "$launcher_mode"
    printf '%s\n' "=================================================="

    rm -f "$json"

    set +e
    PASCAL_LAUNCHER_MODE="$launcher_mode" \
    PASCAL_PYTHON_BIN="$PYTHON_BIN" \
    PASCAL_DIAG_SCRIPT="$DIAG_SCRIPT" \
    PASCAL_OPS_LIB="$PASCAL_LIB" \
      pascalanalyzer \
        -c 1 \
        -r 1 \
        -t man \
        --outp "$json" \
        "$LAUNCHER"
    local rc=$?
    set -e

    printf 'analyzer_rc=%s\n' "$rc"
    summarize_json "$json"
}

# Controle positivo no mesmo ELF: prova que o Analyzer reconhece o launcher linkado.
run_launcher_case linked_selftest selftest

# Testa se o contexto manual configurado para o alvo ELF sobrevive ao exec() do Python.
run_launcher_case linked_exec exec

# Mantem o processo ELF instrumentado vivo enquanto o Python roda em um filho.
run_launcher_case linked_spawn spawn

printf '\n%s\n' "=== TARGET MATRIX SUMMARY ==="
python3 scripts/summarize_pascal_target_matrix.py \
  "$SLURM_SUBMIT_DIR/refactor27_target_linked_selftest.json" \
  "$SLURM_SUBMIT_DIR/refactor27_target_linked_exec.json" \
  "$SLURM_SUBMIT_DIR/refactor27_target_linked_spawn.json"

printf '\n%s\n' "=== TARGET MATRIX COMPLETED ==="
