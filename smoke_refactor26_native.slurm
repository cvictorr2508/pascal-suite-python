#!/bin/bash
#SBATCH --job-name=pascal_smoke_native
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:05:00
#SBATCH --exclusive
#SBATCH --output=smoke26_native_%j.out
#SBATCH --error=smoke26_native_%j.err
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
JSON="$SLURM_SUBMIT_DIR/smoke_pascal_region_native.json"

mkdir -p "$BUILD_DIR"
rm -f "$BIN" "$JSON"

printf '%s\n' "=== HOST ==="
hostname

printf '%s\n' "=== TOOLCHAIN ==="
which gcc
gcc --version | head -1

printf '%s\n' "=== PASCAL ==="
which pascalanalyzer

printf '%s\n' "=== BUILD NATIVE SMOKE ==="
gcc \
    -O2 \
    -std=c11 \
    -I"$PASCAL_ROOT/include" \
    "$SLURM_SUBMIT_DIR/scripts/smoke_pascal_region_native.c" \
    -L"$PASCAL_ROOT/lib" \
    -Wl,-rpath,"$PASCAL_ROOT/lib" \
    -lmpascalops \
    -o "$BIN"

printf '%s\n' "=== LINKAGE ==="
ldd "$BIN" | grep -E 'mpascalops|not found' || true

printf '%s\n' "=== RUN NATIVE SMOKE ==="
pascalanalyzer \
    -c 1 \
    -r 1 \
    -t man \
    --rple sysfs \
    --outp "$JSON" \
    "$BIN"

printf '%s\n' "=== CHECK JSON ==="
test -f "$JSON"
python3 -m json.tool "$JSON" > /dev/null
ls -lh "$JSON"

printf '%s\n' "=== VALIDATE REGIONAL ENERGY CONTRACT ==="
python3 scripts/validate_pascal_energy.py "$JSON"

printf '%s\n' "=== NATIVE SMOKE COMPLETED ==="
