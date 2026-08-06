#!/bin/bash
#SBATCH --job-name=pascal_master
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --time=12:00:00
#SBATCH --exclusive
#SBATCH --output=master_%j.out
#SBATCH --partition=intel-256

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true
set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"
export GRB_LICENSE_FILE="$SLURM_SUBMIT_DIR/secret/gurobi.lic"

echo "=== CONFIGURANDO AMBIENTE PYTHON ==="
if [ ! -d ".venv_313" ]; then
    python3 -m venv .venv_313
fi

source .venv_313/bin/activate
# Instala o PyYAML para ler o nosso novo arquivo
python3 -m pip install pydantic gurobipy pandas pyyaml > /dev/null

# 1. Roda a execução lendo o YAML
python3 rodar_yaml.py meu_experimento.yaml

# 2. Roda a análise logo em seguida (Usaremos o nosso run_analysis.py)
python3 run_analysis_master.py
