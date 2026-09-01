#!/bin/bash
#SBATCH --job-name=pascal_gurobi_scaling
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:10:00
#SBATCH --exclusive
#SBATCH --output=gurobi_scaling27_%j.out
#SBATCH --error=gurobi_scaling27_%j.err
#SBATCH --partition=intel-256

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true

set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"

if [ -f ".venv_313/bin/activate" ]; then
    source .venv_313/bin/activate
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -f "$VIRTUAL_ENV/bin/activate" ]; then
    source "$VIRTUAL_ENV/bin/activate"
elif ! python3 -c 'import gurobipy, yaml' 2>/dev/null; then
    echo "ERROR: nenhum ambiente Python com gurobipy e PyYAML foi encontrado" >&2
    exit 3
fi

export GRB_LICENSE_FILE="$SLURM_SUBMIT_DIR/secret/gurobi.lic"

printf '%s\n' "=== HOST ==="
hostname

printf '%s\n' "=== PYTHON ==="
which python3
python3 --version

printf '%s\n' "=== PASCAL ==="
which pascalanalyzer

printf '%s\n' "=== GUROBI ==="
python3 - <<'PY'
import gurobipy as gp
print("gurobipy", gp.gurobi.version())
PY

printf '%s\n' "=== UNIT TESTS ==="
python3 -m unittest discover -s tests -v

OUTPUT_DIR="$SLURM_SUBMIT_DIR/resultados_finais/refactor27_proxy_scaling"
rm -rf "$OUTPUT_DIR"

printf '%s\n' "=== RUN GUROBI PROXY SCALING [1,2,4] x 1 ==="
python3 rodar_yaml.py refactor27_gurobi_proxy_scaling.yaml

printf '%s\n' "=== OUTPUT FILES ==="
find "$OUTPUT_DIR" -maxdepth 1 -type f -printf '%f\n' | sort

printf '%s\n' "=== VALIDATE GUROBI PROXY SCALING CONTRACT ==="
python3 scripts/validate_refactor27_gurobi_proxy_scaling.py "$OUTPUT_DIR"

printf '%s\n' "=== GUROBI PROXY SCALING COMPLETED ==="
