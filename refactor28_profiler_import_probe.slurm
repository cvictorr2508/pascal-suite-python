#!/bin/bash
#SBATCH --job-name=pascal_prof28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:10:00
#SBATCH --exclusive
#SBATCH --partition=intel-256
#SBATCH --output=profiler28_%j.out
#SBATCH --error=profiler28_%j.err

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true
set -Eeuo pipefail

cd "$SLURM_SUBMIT_DIR"
module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

PASCAL_ROOT=/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08
ANALYZER="$PASCAL_ROOT/bin/pascalanalyzer"
BUILD_DIR="$SLURM_SUBMIT_DIR/.refactor28-build"
SHIM_DIR="$SLURM_SUBMIT_DIR/.refactor28-profiler-shim"
SHIM_LOG="$SLURM_SUBMIT_DIR/refactor28_profiler_shim.log"
PROBE="$BUILD_DIR/refactor28_region_energy_probe"
BASE_JSON="$SLURM_SUBMIT_DIR/refactor28_profiler_baseline.json"
SHIM_JSON="$SLURM_SUBMIT_DIR/refactor28_profiler_shim.json"
BASE_ERR="$SLURM_SUBMIT_DIR/refactor28_profiler_baseline.err"
SHIM_ERR="$SLURM_SUBMIT_DIR/refactor28_profiler_injected.err"

mkdir -p "$BUILD_DIR" "$SHIM_DIR"
rm -f "$SHIM_LOG" "$BASE_JSON" "$SHIM_JSON" "$BASE_ERR" "$SHIM_ERR"

gcc -O2 -std=c11 \
  -I"$PASCAL_ROOT/include" \
  scripts/refactor28_region_energy_probe.c \
  -L"$PASCAL_ROOT/lib" \
  -Wl,-rpath,"$PASCAL_ROOT/lib" \
  -lmpascalops \
  -o "$PROBE"

cat > "$SHIM_DIR/profiler.py" <<'PY'
import os
from pathlib import Path

_LOG = Path(os.environ.get("REFACTOR28_PROFILER_SHIM_LOG", "refactor28_profiler_shim.log"))

def _write(message):
    with _LOG.open("a", encoding="utf-8") as stream:
        stream.write(message + "\n")

_write("profiler_module_imported=true")
_write("profiler_module_file=" + __file__)

class Profiler:
    def __init__(self, *args, **kwargs):
        _write("Profiler_init_args=" + repr(args))
        _write("Profiler_init_kwargs=" + repr(kwargs))
        raise RuntimeError("REFACTOR28_PROFILER_SHIM_CONSTRUCTOR")

def __getattr__(name):
    _write("profiler_getattr=" + str(name))
    raise AttributeError(name)
PY

echo "=== HOST ==="
hostname -f

echo "=== BASELINE ==="
set +e
"$ANALYZER" -c 1 -r 1 -t man --rple perf --outp "$BASE_JSON" "$PROBE" \
  > /dev/null 2> "$BASE_ERR"
base_rc=$?
set -e
echo "baseline_rc=$base_rc"
echo "baseline_json_exists=$([[ -f "$BASE_JSON" ]] && echo true || echo false)"
grep -aE 'profiler|rapl perf|Error' "$BASE_ERR" || true

echo "=== PYTHONPATH SHIM ==="
set +e
PYTHONPATH="$SHIM_DIR${PYTHONPATH:+:$PYTHONPATH}" \
REFACTOR28_PROFILER_SHIM_LOG="$SHIM_LOG" \
PYTHONVERBOSE=1 \
"$ANALYZER" -c 1 -r 1 -t man --rple perf --outp "$SHIM_JSON" "$PROBE" \
  > /dev/null 2> "$SHIM_ERR"
shim_rc=$?
set -e
echo "shim_rc=$shim_rc"
echo "shim_json_exists=$([[ -f "$SHIM_JSON" ]] && echo true || echo false)"
echo "shim_module_imported=$([[ -f "$SHIM_LOG" ]] && echo true || echo false)"

if [[ -f "$SHIM_LOG" ]]; then
  echo "=== SHIM LOG ==="
  cat "$SHIM_LOG"
fi

echo "=== SHIM STDERR MATCHES ==="
grep -aEi 'profiler|rapl|performance_features|REFACTOR28' "$SHIM_ERR" | tail -n 100 || true

echo "=== CLASSIFICATION ==="
if [[ -f "$SHIM_LOG" ]]; then
  echo "external_profiler_import_supported=true"
else
  echo "external_profiler_import_supported=false"
fi

if grep -q '^Profiler_init_' "$SHIM_LOG" 2>/dev/null; then
  echo "Profiler_constructor_reached=true"
else
  echo "Profiler_constructor_reached=false"
fi

echo "baseline_err=$BASE_ERR"
echo "shim_err=$SHIM_ERR"
echo "shim_log=$SHIM_LOG"
echo "=== PROFILER IMPORT PROBE COMPLETED ==="
