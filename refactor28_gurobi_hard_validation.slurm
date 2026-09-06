#!/bin/bash
#SBATCH --job-name=gurobi_hard28
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --exclusive
#SBATCH --partition=intel-128
#SBATCH --output=gurobi_hard28_%j.out
#SBATCH --error=gurobi_hard28_%j.err

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true
set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"

PYTHON_BIN="$SLURM_SUBMIT_DIR/.venv_313/bin/python"
LICENSE_FILE="$SLURM_SUBMIT_DIR/secret/gurobi.lic"
CONFIG_FILE="$SLURM_SUBMIT_DIR/refactor28_gurobi_hard_validation.yaml"
OUTPUT_DIR="$SLURM_SUBMIT_DIR/resultados_finais/refactor28_gurobi_hard_validation"
JSON_FILE="$OUTPUT_DIR/exp_refactor28_gurobi_hard_validation_batch_pascal.json"
BASE_CONFIG_FILE="$OUTPUT_DIR/base_config.json"
SUMMARY_FILE="$OUTPUT_DIR/summary.json"
DATASET_DIR="/home/Projeto_LAMFO_LAPPS/data/facility_location_easy/hard"

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

for instance_id in 5 10 15 20 25; do
    require_file \
        "$DATASET_DIR/CFL_hard_instance_${instance_id}.lp.gz" \
        "workload_missing_or_empty"
done

export GRB_LICENSE_FILE="$LICENSE_FILE"

printf 'host=%s\n' "$(hostname -f)"
printf 'python=%s\n' "$PYTHON_BIN"
printf 'config=%s\n' "$CONFIG_FILE"
printf 'partition=%s\n' "${SLURM_JOB_PARTITION:-unknown}"
printf 'campaign_attempts=%s\n' "90"

"$PYTHON_BIN" rodar_yaml.py "$CONFIG_FILE"

require_file "$JSON_FILE" "analyzer_json_missing_or_empty"
require_file "$BASE_CONFIG_FILE" "base_config_missing_or_empty"

"$PYTHON_BIN" scripts/summarize_refactor28_nested_energy.py \
    "$JSON_FILE" \
    --base-config "$BASE_CONFIG_FILE" \
    --require-runs 5 \
    --require-configurations 15 \
    --max-median-error-percent 5 \
    --preferred-max-cv-percent 10 \
    --output-json "$SUMMARY_FILE"

printf 'validation_json=%s\n' "$JSON_FILE"
printf 'validation_summary=%s\n' "$SUMMARY_FILE"
