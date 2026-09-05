#!/bin/bash
#SBATCH --job-name=gurobi_nested28
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=00:10:00
#SBATCH --exclusive
#SBATCH --partition=intel-128
#SBATCH --output=gurobi_nested28_%j.out
#SBATCH --error=gurobi_nested28_%j.err

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true
set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"

PYTHON_BIN="$SLURM_SUBMIT_DIR/.venv_313/bin/python"
LICENSE_FILE="$SLURM_SUBMIT_DIR/secret/gurobi.lic"
CONFIG_FILE="$SLURM_SUBMIT_DIR/refactor28_gurobi_nested_smoke.yaml"
WORKLOAD_FILE="/home/Projeto_LAMFO_LAPPS/data/facility_location_easy/hard/CFL_hard_instance_20.lp.gz"

require_executable() {
    local path="$1"
    local label="$2"
    if [[ ! -x "$path" ]]; then
        printf 'preflight_error=%s path=%s\n' "$label" "$path" >&2
        exit 10
    fi
}

require_file() {
    local path="$1"
    local label="$2"
    if [[ ! -s "$path" ]]; then
        printf 'preflight_error=%s path=%s\n' "$label" "$path" >&2
        exit 11
    fi
}

require_executable "$PYTHON_BIN" "python_missing_or_not_executable"
require_file "$LICENSE_FILE" "gurobi_license_missing_or_empty"
require_file "$CONFIG_FILE" "configuration_missing_or_empty"
require_file "$WORKLOAD_FILE" "workload_missing_or_empty"

if ! command -v gzip >/dev/null 2>&1; then
    printf 'preflight_error=gzip_not_found\n' >&2
    exit 12
fi

export GRB_LICENSE_FILE="$LICENSE_FILE"

printf 'host=%s\n' "$(hostname -f)"
printf 'python=%s\n' "$PYTHON_BIN"
printf 'config=%s\n' "$CONFIG_FILE"
printf 'workload=%s\n' "$WORKLOAD_FILE"
printf 'partition=%s\n' "${SLURM_JOB_PARTITION:-unknown}"

"$PYTHON_BIN" rodar_yaml.py "$CONFIG_FILE"
