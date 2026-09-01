#!/bin/bash
#SBATCH --job-name=pascal_proxy27
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:10:00
#SBATCH --exclusive
#SBATCH --output=proxy27_%j.out
#SBATCH --error=proxy27_%j.err
#SBATCH --partition=intel-256

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true

set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"

PASCAL_ROOT="/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08"
PYTHON_BIN="$(command -v python3)"
BUILD_DIR="$SLURM_SUBMIT_DIR/.refactor27-build"
PROXY="$BUILD_DIR/pascal_region_proxy_launcher"
SCRIPT="$SLURM_SUBMIT_DIR/scripts/diagnose_pascal_region_proxy.py"
JSON="$SLURM_SUBMIT_DIR/refactor27_region_proxy.json"

mkdir -p "$BUILD_DIR"
rm -f "$PROXY" "$JSON"

printf '%s\n' "=== HOST ==="
hostname

printf '%s\n' "=== PYTHON ==="
printf 'python=%s\n' "$PYTHON_BIN"
python3 --version

printf '%s\n' "=== PASCAL ==="
command -v pascalanalyzer

printf '%s\n' "=== UNIT TESTS ==="
python3 -m unittest discover -s tests -v

printf '%s\n' "=== BUILD REGION PROXY ==="
gcc \
    -O2 \
    -std=c11 \
    -I"$PASCAL_ROOT/include" \
    "$SLURM_SUBMIT_DIR/scripts/pascal_region_proxy_launcher.c" \
    -L"$PASCAL_ROOT/lib" \
    -Wl,-rpath,"$PASCAL_ROOT/lib" \
    -lmpascalops \
    -o "$PROXY"

printf '%s\n' "=== PROXY ELF NEEDED ==="
readelf -d "$PROXY" | grep NEEDED || true

printf '%s\n' "=== PROXY LINKAGE ==="
ldd "$PROXY" | grep -E 'mpascalops|not found' || true

printf '%s\n' "=== RUN REGION PROXY ==="
PASCAL_PYTHON_BIN="$PYTHON_BIN" \
PASCAL_PROXY_SCRIPT="$SCRIPT" \
  pascalanalyzer \
    -c 1 \
    -r 1 \
    -t man \
    --outp "$JSON" \
    "$PROXY"

printf '%s\n' "=== CHECK JSON ==="
test -f "$JSON"
python3 -m json.tool "$JSON" > /dev/null
ls -lh "$JSON"

printf '%s\n' "=== VALIDATE REGION 1 ==="
python3 - "$JSON" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
data = payload.get("data") or {}

samples = []
for run_key, run in data.items():
    regions = run.get("regions") if isinstance(run, dict) else None
    print(f"run={run_key} regions={regions}")
    if isinstance(regions, dict):
        samples.extend(regions.get("1") or [])

if not samples:
    print("proxy_region_1=false")
    raise SystemExit(2)

first = samples[0]
duration = float(first[1]) - float(first[0])
print("proxy_region_1=true")
print(f"proxy_region_1_duration_s={duration:.9f}")
print(f"proxy_region_1_sample={first}")

if not 1.5 <= duration <= 2.5:
    print("proxy_duration_compatible=false")
    raise SystemExit(3)

print("proxy_duration_compatible=true")
PY

printf '%s\n' "=== REGION PROXY COMPLETED ==="
