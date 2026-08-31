#!/bin/bash
#SBATCH --job-name=pascal_loader_matrix
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:10:00
#SBATCH --exclusive
#SBATCH --output=loader27_%j.out
#SBATCH --error=loader27_%j.err
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
BUILD_DIR="$SLURM_SUBMIT_DIR/.refactor27-build"
WRAPPER="$BUILD_DIR/pascal_loader_wrapper.sh"

mkdir -p "$BUILD_DIR"
cp scripts/pascal_loader_wrapper.sh "$WRAPPER"
chmod 700 "$WRAPPER"

printf '%s\n' "=== HOST ==="
hostname

printf '%s\n' "=== PYTHON ==="
"$PYTHON_BIN" --version
printf 'python=%s\n' "$PYTHON_BIN"

printf '%s\n' "=== PASCAL ==="
which pascalanalyzer
printf 'pascal_lib=%s\n' "$PASCAL_LIB"

printf '%s\n' "=== UNIT TESTS ==="
"$PYTHON_BIN" -m unittest discover -s tests -v

run_case() {
    local mode="$1"
    local json="$SLURM_SUBMIT_DIR/refactor27_loader_${mode}.json"

    printf '\n==================================================\n'
    printf 'MODE=%s\n' "$mode"
    printf '==================================================\n'

    rm -f "$json"

    set +e
    PASCAL_LOADER_MODE="$mode" \
    PASCAL_OPS_LIB="$PASCAL_LIB" \
    PASCAL_DIAG_PYTHON="$PYTHON_BIN" \
    pascalanalyzer \
        -c 1 \
        -r 1 \
        -t man \
        --outp "$json" \
        "$WRAPPER"
    local analyzer_rc=$?
    set -e

    printf 'analyzer_rc=%s\n' "$analyzer_rc"

    if [ -f "$json" ]; then
        "$PYTHON_BIN" -m json.tool "$json" > /dev/null
        printf 'json=%s\n' "$json"
        "$PYTHON_BIN" - <<PY
import json
from pathlib import Path
path = Path(r"$json")
payload = json.loads(path.read_text(encoding="utf-8"))
data = payload.get("data", {}) or {}
print("run_keys=", list(data))
for key, run in data.items():
    if isinstance(run, dict):
        print("run=", key, "regions=", run.get("regions"))
PY
    else
        printf 'json_missing=%s\n' "$json"
    fi
}

run_case baseline
run_case preload
run_case rtld_global

printf '\n=== MATRIX SUMMARY ===\n'
"$PYTHON_BIN" scripts/summarize_pascal_loader_matrix.py \
    "$SLURM_SUBMIT_DIR/refactor27_loader_baseline.json" \
    "$SLURM_SUBMIT_DIR/refactor27_loader_preload.json" \
    "$SLURM_SUBMIT_DIR/refactor27_loader_rtld_global.json"

printf '%s\n' "=== LOADER MATRIX COMPLETED ==="
