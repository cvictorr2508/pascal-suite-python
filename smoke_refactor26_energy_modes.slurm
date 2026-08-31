#!/bin/bash
#SBATCH --job-name=pascal_energy_modes
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:10:00
#SBATCH --exclusive
#SBATCH --output=energy_modes_%j.out
#SBATCH --error=energy_modes_%j.err
#SBATCH --partition=intel-256

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true

set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"

PASCAL_ROOT="/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08"
BUILD_DIR="$SLURM_SUBMIT_DIR/.refactor26-build"
BIN="$BUILD_DIR/smoke_pascal_region_native"

mkdir -p "$BUILD_DIR"

echo "=== BUILD ==="
gcc \
    -O2 \
    -std=c11 \
    -I"$PASCAL_ROOT/include" \
    "$SLURM_SUBMIT_DIR/scripts/smoke_pascal_region_native.c" \
    -L"$PASCAL_ROOT/lib" \
    -Wl,-rpath,"$PASCAL_ROOT/lib" \
    -lmpascalops \
    -o "$BIN"

ldd "$BIN" | grep -E 'mpascalops|not found' || true

run_case() {
    local name="$1"
    shift
    local json="$SLURM_SUBMIT_DIR/smoke_energy_${name}.json"

    echo
    echo "=================================================="
    echo "CASE=$name"
    echo "FLAGS=$*"
    echo "=================================================="

    rm -f "$json"

    pascalanalyzer \
        -c 1 \
        -r 1 \
        -t man \
        "$@" \
        --outp "$json" \
        "$BIN"

    test -f "$json"
    python3 -m json.tool "$json" > /dev/null

    echo "--- RAW CONTRACT SUMMARY ---"
    python3 scripts/inspect_pascal_energy_json.py "$json"

    echo "--- REGIONAL ENERGY VALIDATOR ---"
    set +e
    python3 scripts/validate_pascal_energy.py "$json"
    local validator_rc=$?
    set -e
    echo "validator_rc=$validator_rc"
}

# Baseline already observed: whole-program RAPL energy only.
run_case rple --rple sysfs

# Main hypothesis: sampled RAPL is required to derive energy per instrumented region.
run_case rpls --rpls sysfs

# Check whether whole-program and regional energy can coexist in the same Analyzer run.
run_case both --rple sysfs --rpls sysfs

echo
echo "=== ENERGY MODE MATRIX COMPLETED ==="
