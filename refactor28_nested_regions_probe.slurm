#!/bin/bash
#SBATCH --job-name=pascal_nested28
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --exclusive
#SBATCH --output=nested28_%j.out
#SBATCH --error=nested28_%j.err
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
PROBE="$BUILD_DIR/refactor28_nested_regions_probe"

mkdir -p "$BUILD_DIR"

gcc -O2 -std=c11 \
  -I"$PASCAL_ROOT/include" \
  scripts/refactor28_nested_regions_probe.c \
  -L"$PASCAL_ROOT/lib" \
  -Wl,-rpath,"$PASCAL_ROOT/lib" \
  -lmpascalops \
  -o "$PROBE"

printf 'host=%s\n' "$(hostname -f)"
printf 'probe=%s\n' "$PROBE"

run_case() {
    local name="$1"
    local aggregation_level="$2"
    local json="$SLURM_SUBMIT_DIR/refactor28_nested_${name}.json"
    local stdout_log="$SLURM_SUBMIT_DIR/refactor28_nested_${name}.stdout"
    local stderr_log="$SLURM_SUBMIT_DIR/refactor28_nested_${name}.stderr"

    rm -f "$json" "$stdout_log" "$stderr_log"

    printf '\n=== CASE %s ===\n' "$name"
    set +e
    "$ANALYZER" \
      -c 1 \
      -r 1 \
      -t man \
      -a "$aggregation_level" \
      --rple sysfs \
      --rpls sysfs \
      --outp "$json" \
      "$PROBE" \
      >"$stdout_log" 2>"$stderr_log"
    local analyzer_rc=$?
    set -e

    printf 'analyzer_rc=%s\n' "$analyzer_rc"
    if (( analyzer_rc != 0 )); then
        sed -n '1,160p' "$stderr_log"
        return "$analyzer_rc"
    fi

    python3 - "$json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
with path.open("r", encoding="utf-8") as stream:
    document = json.load(stream)

required = {"0", "1", "2"}
data = document.get("data") or {}
if not data:
    raise SystemExit("JSON sem execuções em data")

for run_key, run in data.items():
    regions = run.get("regions") or {}
    present = set(regions)
    print(f"run={run_key}")
    print(f"region_ids={sorted(present)}")
    print(f"regions={regions}")

    missing = required - present
    if missing:
        raise SystemExit(f"regiões ausentes: {sorted(missing)}")

    intervals = {}
    for region_id in sorted(required):
        entries = regions.get(region_id)
        if not isinstance(entries, list) or not entries:
            raise SystemExit(f"região {region_id} sem intervalo")
        intervals[region_id] = (float(entries[0][0]), float(entries[0][1]))

    start0, stop0 = intervals["0"]
    start1, stop1 = intervals["1"]
    start2, stop2 = intervals["2"]
    ordered = start0 <= start1 < stop1 <= start2 < stop2 <= stop0
    print(f"nested_intervals_valid={ordered}")
    if not ordered:
        raise SystemExit("intervalos não formam a hierarquia esperada")

    sensors = run.get("sensors") or {}
    sample_count = sum(
        len(samples)
        for name, samples in sensors.items()
        if str(name).startswith("rapl_sample") and isinstance(samples, list)
    )
    print(f"rapl_sample_count={sample_count}")
    print(f"global_rapl={run.get('rapl-sysfs')}")
    if sample_count < 2:
        raise SystemExit("amostras RAPL insuficientes")
PY
}

run_case no_aggregation 0
run_case aggregation 1

printf '\n=== NESTED REGION PROBE COMPLETED ===\n'
