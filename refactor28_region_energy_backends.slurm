#!/bin/bash
#SBATCH --job-name=pascal_energy28
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:10:00
#SBATCH --exclusive
#SBATCH --output=energy28_%j.out
#SBATCH --error=energy28_%j.err
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
BUILD_DIR="$SLURM_SUBMIT_DIR/.refactor28-build"
PROBE="$BUILD_DIR/refactor28_region_energy_probe"

mkdir -p "$BUILD_DIR"
rm -f "$PROBE"

printf '%s\n' "=== HOST ==="
hostname

printf '%s\n' "=== PASCAL BUILD ==="
command -v pascalanalyzer
printf 'pascal_root=%s\n' "$PASCAL_ROOT"
file "$(command -v pascalanalyzer)"

printf '%s\n' "=== PERF/RAPL ENVIRONMENT ==="
printf 'perf_event_paranoid='
cat /proc/sys/kernel/perf_event_paranoid 2>/dev/null || true
command -v perf || true
if command -v perf >/dev/null 2>&1; then
    perf list 2>/dev/null | grep -iE 'energy|power' || true
fi

printf '%s\n' "=== UNIT TESTS ==="
python3 -m unittest discover -s tests -v

printf '%s\n' "=== BUILD NATIVE PROBE ==="
gcc \
    -O2 \
    -std=c11 \
    -I"$PASCAL_ROOT/include" \
    "$SLURM_SUBMIT_DIR/scripts/refactor28_region_energy_probe.c" \
    -L"$PASCAL_ROOT/lib" \
    -Wl,-rpath,"$PASCAL_ROOT/lib" \
    -lmpascalops \
    -o "$PROBE"

readelf -d "$PROBE" | grep NEEDED || true
ldd "$PROBE" | grep -E 'mpascalops|not found' || true

run_case() {
    local mode="$1"
    shift
    local json="$SLURM_SUBMIT_DIR/refactor28_energy_${mode}.json"

    printf '\n==================================================\n'
    printf 'CASE=%s\n' "$mode"
    printf 'ARGS='
    printf '%q ' "$@"
    printf '\n==================================================\n'

    rm -f "$json"
    set +e
    pascalanalyzer \
        -c 1 \
        -r 1 \
        -t man \
        --outp "$json" \
        "$@" \
        "$PROBE"
    local rc=$?
    set -e

    printf 'analyzer_rc=%s\n' "$rc"
    printf 'json=%s\n' "$json"

    if [ -f "$json" ]; then
        python3 -m json.tool "$json" >/dev/null
        python3 - "$json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
descriptor = ((payload.get("config") or {}).get("data_descriptor") or {})
print("descriptor_values=", descriptor.get("values"))
print("descriptor_extras=", descriptor.get("extras"))
for run_key, run in (payload.get("data") or {}).items():
    if isinstance(run, dict):
        print("run=", run_key)
        print("regions=", run.get("regions"))
        print("rapl_keys=", sorted(k for k in run if str(k).startswith("rapl")))
        print("sensors=", run.get("sensors"))
PY
    else
        printf 'json_missing=true\n'
    fi
}

run_case rple_sysfs --rple sysfs
run_case rple_perf --rple perf
run_case rpls_sysfs --rpls sysfs
run_case rpls_perf --rpls perf
run_case rple_perf_rpls_perf --rple perf --rpls perf
run_case rple_sysfs_rpls_perf --rple sysfs --rpls perf

printf '\n=== MATRIX SUMMARY ===\n'
python3 scripts/summarize_refactor28_region_energy.py \
    "$SLURM_SUBMIT_DIR/refactor28_energy_rple_sysfs.json" \
    "$SLURM_SUBMIT_DIR/refactor28_energy_rple_perf.json" \
    "$SLURM_SUBMIT_DIR/refactor28_energy_rpls_sysfs.json" \
    "$SLURM_SUBMIT_DIR/refactor28_energy_rpls_perf.json" \
    "$SLURM_SUBMIT_DIR/refactor28_energy_rple_perf_rpls_perf.json" \
    "$SLURM_SUBMIT_DIR/refactor28_energy_rple_sysfs_rpls_perf.json"

printf '%s\n' "=== REFACTOR 28 BACKEND MATRIX COMPLETED ==="
