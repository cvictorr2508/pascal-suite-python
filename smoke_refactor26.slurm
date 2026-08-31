#!/bin/bash
#SBATCH --job-name=pascal_smoke
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:05:00
#SBATCH --exclusive
#SBATCH --output=smoke26_%j.out
#SBATCH --error=smoke26_%j.err
#SBATCH --partition=intel-256

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true

set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"

chmod +x scripts/smoke_pascal_region_wrapper.sh

printf '%s\n' "=== HOST ==="
hostname

printf '%s\n' "=== PYTHON ==="
which python3
python3 --version

printf '%s\n' "=== PASCAL ==="
which pascalanalyzer

printf '%s\n' "=== BINDING ==="
python3 scripts/check_pascalops_symbols.py

printf '%s\n' "=== UNIT TESTS ==="
python3 -m unittest discover -s tests -v

printf '%s\n' "=== CLEAN PREVIOUS RESULT ==="
rm -f smoke_pascal_region.json

printf '%s\n' "=== RUN SMOKE ==="
pascalanalyzer \
    -c 1 \
    -r 1 \
    -t man \
    --rple sysfs \
    --outp smoke_pascal_region.json \
    "$SLURM_SUBMIT_DIR/scripts/smoke_pascal_region_wrapper.sh"

printf '%s\n' "=== CHECK JSON ==="
test -f smoke_pascal_region.json
python3 -m json.tool smoke_pascal_region.json > /dev/null
ls -lh smoke_pascal_region.json

printf '%s\n' "=== VALIDATE REGIONAL ENERGY CONTRACT ==="
python3 scripts/validate_pascal_energy.py smoke_pascal_region.json

printf '%s\n' "=== SMOKE COMPLETED ==="
