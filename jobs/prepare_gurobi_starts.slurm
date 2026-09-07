#!/bin/bash
#SBATCH --job-name=gurobi_starts
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --exclusive
#SBATCH --partition=intel-128
#SBATCH --output=gurobi_starts_%j.out
#SBATCH --error=gurobi_starts_%j.err

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true
set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8

cd "$SLURM_SUBMIT_DIR"

PYTHON_BIN="${PASCAL_PYTHON_BIN:-$(command -v python || true)}"
LICENSE_FILE="${GRB_LICENSE_FILE:-$SLURM_SUBMIT_DIR/secret/gurobi.lic}"
DATASET_DIR="${CFL_HARD_DIR:-/home/Projeto_LAMFO_LAPPS/data/facility_location_easy/hard}"
OUTPUT_DIR="${GUROBI_START_DIR:-$SLURM_SUBMIT_DIR/initial_solutions/gurobi}"

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
    printf 'preflight_error=python_not_available_on_path\n' >&2
    exit 10
fi
if [[ ! -s "$LICENSE_FILE" ]]; then
    printf 'preflight_error=gurobi_license_missing_or_empty path=%s\n' \
        "$LICENSE_FILE" >&2
    exit 11
fi

export GRB_LICENSE_FILE="$LICENSE_FILE"
mkdir -p "$OUTPUT_DIR"

for instance_id in 5 10 15 20 25; do
    workload="$DATASET_DIR/CFL_hard_instance_${instance_id}.lp.gz"
    output="$OUTPUT_DIR/CFL_hard_instance_${instance_id}.mst"
    if [[ ! -s "$workload" ]]; then
        printf 'preflight_error=workload_missing_or_empty path=%s\n' \
            "$workload" >&2
        exit 11
    fi
    "$PYTHON_BIN" scripts/export_gurobi_warm_start.py \
        "$workload" "$output" --threads 1 --seed 10000
done

sha256sum "$OUTPUT_DIR"/*.mst "$OUTPUT_DIR"/*.mst.json \
    > "$OUTPUT_DIR/SHA256SUMS"
printf 'warm_start_directory=%s\n' "$OUTPUT_DIR"

