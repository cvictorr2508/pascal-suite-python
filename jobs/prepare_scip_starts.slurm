#!/bin/bash
#SBATCH --job-name=scip_starts
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --exclusive
#SBATCH --partition=intel-128
#SBATCH --output=scip_starts_%j.out
#SBATCH --error=scip_starts_%j.err

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true
set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8

cd "$SLURM_SUBMIT_DIR"

PYTHON_BIN="${PASCAL_PYTHON_BIN:-$(command -v python || true)}"
DATASET_DIR="${CFL_HARD_DIR:-/home/Projeto_LAMFO_LAPPS/data/facility_location_easy/hard}"
OUTPUT_DIR="${SCIP_START_DIR:-$SLURM_SUBMIT_DIR/initial_solutions/scip}"

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
    printf 'preflight_error=python_not_available_on_path\n' >&2
    exit 10
fi
if ! "$PYTHON_BIN" -c 'import pyscipopt' >/dev/null 2>&1; then
    printf 'preflight_error=pyscipopt_not_available\n' >&2
    exit 10
fi

mkdir -p "$OUTPUT_DIR"
for instance_id in 5 10 15 20 25; do
    workload="$DATASET_DIR/CFL_hard_instance_${instance_id}.lp.gz"
    output="$OUTPUT_DIR/CFL_hard_instance_${instance_id}.sol"
    if [[ ! -s "$workload" ]]; then
        printf 'preflight_error=workload_missing_or_empty path=%s\n' \
            "$workload" >&2
        exit 11
    fi
    "$PYTHON_BIN" scripts/export_scip_warm_start.py \
        "$workload" "$output" --seed 10000
done

sha256sum "$OUTPUT_DIR"/*.sol "$OUTPUT_DIR"/*.sol.json \
    > "$OUTPUT_DIR/SHA256SUMS"
printf 'warm_start_directory=%s\n' "$OUTPUT_DIR"
