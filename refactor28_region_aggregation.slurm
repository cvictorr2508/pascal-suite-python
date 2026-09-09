#!/bin/bash
#SBATCH --job-name=pascal_agg28
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:10:00
#SBATCH --exclusive
#SBATCH --output=agg28_%j.out
#SBATCH --error=agg28_%j.err
#SBATCH --partition=intel-128

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true
set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"

PASCAL_ROOT="/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08"
ANALYZER="$PASCAL_ROOT/bin/pascalanalyzer"
BUILD_DIR="$SLURM_SUBMIT_DIR/.refactor28-build"
PROBE="$BUILD_DIR/refactor28_region_energy_probe"

mkdir -p "$BUILD_DIR"

gcc -O2 -std=c11 \
  -I"$PASCAL_ROOT/include" \
  scripts/refactor28_region_energy_probe.c \
  -L"$PASCAL_ROOT/lib" \
  -Wl,-rpath,"$PASCAL_ROOT/lib" \
  -lmpascalops \
  -o "$PROBE"

printf '%s\n' "=== HOST ==="
hostname -f
printf 'analyzer=%s\n' "$ANALYZER"
file "$ANALYZER"
printf '%s\n' "=== AGGREGATION HELP ==="
"$ANALYZER" -h 2>&1 | grep -aE -- '-a LEVEL|--ragl|--ragt|--rpls|--rple' || true

JSONS=()

run_case() {
    local name="$1"
    local level="$2"
    shift 2

    local json="$SLURM_SUBMIT_DIR/refactor28_agg_${name}.json"
    local stdout_log="$SLURM_SUBMIT_DIR/refactor28_agg_${name}.stdout"
    local stderr_log="$SLURM_SUBMIT_DIR/refactor28_agg_${name}.stderr"

    rm -f "$json" "$stdout_log" "$stderr_log"

    echo
    printf '%s\n' "=== CASE $name ==="
    printf 'aggregation_level=%s\n' "$level"
    printf 'extra_args='
    printf '%q ' "$@"
    echo

    set +e
    "$ANALYZER" \
      -c 1 \
      -r 1 \
      -t man \
      -a "$level" \
      --outp "$json" \
      "$@" \
      "$PROBE" \
      > "$stdout_log" 2> "$stderr_log"
    local rc=$?
    set -e

    printf 'analyzer_rc=%s\n' "$rc"
    printf 'json_exists=%s\n' "$([[ -f "$json" ]] && echo true || echo false)"

    if [[ -s "$stderr_log" ]]; then
        echo "--- analyzer stderr matches ---"
        grep -aEi 'error|warning|rapl|region|aggregat' "$stderr_log" || true
    fi

    if [[ -f "$json" ]]; then
        JSONS+=("$json")
        python3 - "$json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
with path.open("r", encoding="utf-8") as stream:
    doc = json.load(stream)

descriptor = doc.get("config", {}).get("data_descriptor", {})
print("descriptor_values=", descriptor.get("values"))
print("descriptor_extras=", descriptor.get("extras"))

for key, run in (doc.get("data") or {}).items():
    print("run_key=", key)
    print("run_keys=", sorted(run.keys()))
    print("regions=", run.get("regions"))
    print("sensors=", run.get("sensors"))
    for name, value in run.items():
        lname = str(name).lower()
        if "rapl" in lname or "energy" in lname:
            print(f"energy_like[{name}]=", value)
PY
    fi
}

# Control: previously observed sampled RAPL without aggregation.
run_case control_rpls_sysfs 0 --rpls sysfs

# Thesis-documented regional aggregation mode, applied to RAPL sample energy.
run_case agg_rpls_sysfs 1 --rpls sysfs

# Whole-program begin/end RAPL with regional aggregation enabled.
run_case agg_rple_sysfs 1 --rple sysfs

# Both whole-program and sampled RAPL under regional aggregation.
run_case agg_both_sysfs 1 --rple sysfs --rpls sysfs

# Alternate accumulated-time aggregation implementation exposed by current CLI.
run_case agg_rpls_sysfs_acc 1 --ragt acc --rpls sysfs
run_case agg_both_sysfs_acc 1 --ragt acc --rple sysfs --rpls sysfs

echo
printf '%s\n' "=== REGION ENERGY VALIDATION ==="
if [[ ${#JSONS[@]} -gt 0 ]]; then
    set +e
    python3 scripts/summarize_refactor28_region_energy.py "${JSONS[@]}"
    summary_rc=$?
    set -e
    printf 'summary_rc=%s\n' "$summary_rc"
else
    echo "no_json_outputs=true"
fi

printf '%s\n' "=== REFACTOR 28 REGIONAL AGGREGATION GATE COMPLETED ==="
