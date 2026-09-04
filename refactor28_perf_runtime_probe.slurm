#!/bin/bash
#SBATCH --job-name=pascal_perf28
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:10:00
#SBATCH --exclusive
#SBATCH --output=perf28_%j.out
#SBATCH --error=perf28_%j.err
#SBATCH --partition=intel-256

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true
set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"

PASCAL_ROOT="/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08"
ANALYZER="$PASCAL_ROOT/bin/pascalanalyzer"
PYTHON_BIN="$(command -v python3)"

printf '%s\n' "=== HOST ==="
hostname

printf '%s\n' "=== PASCAL ANALYZER ==="
printf 'analyzer=%s\n' "$ANALYZER"
file "$ANALYZER"

printf '%s\n' "=== PYTHON MODULE PROFILER ==="
printf 'python=%s\n' "$PYTHON_BIN"
"$PYTHON_BIN" - <<'PY'
import importlib.util
import sys
spec = importlib.util.find_spec("profiler")
print("python_version=", sys.version.replace("\n", " "))
print("profiler_spec=", spec)
if spec is not None:
    print("profiler_origin=", spec.origin)
    print("profiler_locations=", list(spec.submodule_search_locations or []))
PY

printf '%s\n' "=== INSTALLED TREE: PROFILER/PERF REFERENCES ==="
find "$PASCAL_ROOT" -type f \( -iname '*profiler*' -o -iname '*perf*' \) -print 2>/dev/null | sort || true
printf '%s\n' "--- text files mentioning profiler ---"
grep -RIl --exclude='*.so' --exclude='pascalanalyzer' 'profiler' "$PASCAL_ROOT" 2>/dev/null | sort || true

printf '%s\n' "=== ANALYZER PACKAGING STRINGS ==="
strings "$ANALYZER" | grep -E 'PyInstaller|_MEIPASS|PYZ|profiler|rapl[-_].*perf' | sort -u | sed -n '1,120p' || true

printf '%s\n' "=== PERF ENVIRONMENT ==="
printf 'perf_event_paranoid='
cat /proc/sys/kernel/perf_event_paranoid
command -v perf
perf list 2>/dev/null | grep -E 'power/energy-(pkg|ram|cores)/' || true

printf '%s\n' "=== DIRECT PERF RAPL PROBE ==="
PERF_LOG="$SLURM_SUBMIT_DIR/perf28_direct_${SLURM_JOB_ID}.txt"
rm -f "$PERF_LOG"
set +e
perf stat -a \
    -e power/energy-pkg/ \
    -e power/energy-ram/ \
    -- sleep 2 \
    > /dev/null 2> "$PERF_LOG"
PERF_RC=$?
set -e
printf 'direct_perf_rc=%s\n' "$PERF_RC"
cat "$PERF_LOG"

printf '%s\n' "=== CLASSIFICATION ==="
if [ "$PERF_RC" -eq 0 ]; then
    echo "direct_perf_rapl_available=true"
else
    echo "direct_perf_rapl_available=false"
fi

if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("profiler") else 1)
PY
then
    echo "python_profiler_available=true"
else
    echo "python_profiler_available=false"
fi

printf '%s\n' "=== PERF RUNTIME PROBE COMPLETED ==="
