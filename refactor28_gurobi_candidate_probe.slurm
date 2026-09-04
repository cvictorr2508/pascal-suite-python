#!/bin/bash
#SBATCH --job-name=gurobi_probe28
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=00:10:00
#SBATCH --array=0-4%1
#SBATCH --output=gurobi_probe28_%A_%a.out
#SBATCH --error=gurobi_probe28_%A_%a.err
#SBATCH --partition=intel-256

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true
set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8

cd "$SLURM_SUBMIT_DIR"

candidate_ids=(5 10 15 20 25)
task_index="${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"
if (( task_index < 0 || task_index >= ${#candidate_ids[@]} )); then
    echo "invalid array index: $task_index" >&2
    exit 2
fi

candidate_id="${candidate_ids[$task_index]}"
dataset_dir="${CFL_HARD_DIR:-/home/Projeto_LAMFO_LAPPS/data/facility_location_easy/hard}"
workload="$dataset_dir/CFL_hard_instance_${candidate_id}.lp"
output_dir="${GUROBI_PROBE_OUTPUT_DIR:-$SLURM_SUBMIT_DIR/resultados_finais/refactor28_gurobi_candidate_probe}"
python_bin="$SLURM_SUBMIT_DIR/.venv_313/bin/python"
license_file="$SLURM_SUBMIT_DIR/secret/gurobi.lic"

test -s "$workload" || { echo "missing workload: $workload" >&2; exit 3; }
test -x "$python_bin" || { echo "missing Python environment: $python_bin" >&2; exit 4; }
test -s "$license_file" || { echo "missing Gurobi license: $license_file" >&2; exit 5; }

export GRB_LICENSE_FILE="$license_file"
mkdir -p "$output_dir"

printf 'host=%s\n' "$(hostname)"
printf 'job=%s task=%s instance=%s\n' "$SLURM_ARRAY_JOB_ID" "$task_index" "$candidate_id"
printf 'workload=%s\n' "$workload"
printf 'output_dir=%s\n' "$output_dir"

"$python_bin" scripts/probe_gurobi_candidate.py \
    --workload "$workload" \
    --output-dir "$output_dir" \
    --threads 1 \
    --time-limit 60 \
    --seed 10000
