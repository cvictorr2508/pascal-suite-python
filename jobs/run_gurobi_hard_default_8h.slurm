#!/bin/bash
#SBATCH --job-name=gurobi_default8h
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --partition=intel-128
#SBATCH --output=gurobi_default8h_%A_%a.out
#SBATCH --error=gurobi_default8h_%A_%a.err

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true
set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"

CONFIG_FILE="${PASCAL_EXPERIMENT_CONFIG:-experiments/gurobi-hard-default-8h.yaml}"
CAMPAIGN_ROOT="${PASCAL_CAMPAIGN_ROOT:?PASCAL_CAMPAIGN_ROOT is required}"
PYTHON_BIN="${PASCAL_PYTHON_BIN:-$(command -v python || true)}"
LICENSE_FILE="${GRB_LICENSE_FILE:-$SLURM_SUBMIT_DIR/secret/gurobi.lic}"

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
    printf '%s\n' 'preflight_error=python_not_available_on_path' >&2
    exit 10
fi
for required in "$CONFIG_FILE" "$LICENSE_FILE"; do
    if [[ ! -s "$required" ]]; then
        printf 'preflight_error=required_file_missing path=%s\n' "$required" >&2
        exit 11
    fi
done
if [[ ! "${SLURM_ARRAY_TASK_ID:-}" =~ ^([0-9]|1[0-4])$ ]]; then
    printf 'preflight_error=invalid_array_index value=%s\n' \
        "${SLURM_ARRAY_TASK_ID:-missing}" >&2
    exit 12
fi
if [[ "${PASCAL_SOURCE_TRACKED_CLEAN:-}" != "true" ]]; then
    printf 'preflight_error=tracked_worktree_not_clean value=%s\n' \
        "${PASCAL_SOURCE_TRACKED_CLEAN:-missing}" >&2
    exit 12
fi

export GRB_LICENSE_FILE="$LICENSE_FILE"
export PASCAL_SLURM_ALLOCATION_MODE=exclusive
if command -v scontrol >/dev/null 2>&1; then
    scheduler_record="$(scontrol show job -o "$SLURM_JOB_ID" 2>/dev/null || true)"
    scheduler_oversubscribe="$(
        printf '%s\n' "$scheduler_record" |
            tr ' ' '\n' |
            awk -F= '$1 == "OverSubscribe" { print $2; exit }'
    )"
    export PASCAL_SLURM_OVERSUBSCRIBE="$scheduler_oversubscribe"
fi

printf 'host=%s\n' "$(hostname -f)"
printf 'python=%s\n' "$PYTHON_BIN"
printf 'python_version=%s\n' "$("$PYTHON_BIN" --version 2>&1)"
printf 'source_commit=%s\n' "${PASCAL_SOURCE_COMMIT:-unknown}"
printf 'source_branch=%s\n' "${PASCAL_SOURCE_BRANCH:-detached}"
printf 'source_tracked_clean=%s\n' "${PASCAL_SOURCE_TRACKED_CLEAN:-unknown}"
printf 'config=%s\n' "$CONFIG_FILE"
printf 'campaign_root=%s\n' "$CAMPAIGN_ROOT"
printf 'array_job_id=%s\n' "${SLURM_ARRAY_JOB_ID:-unknown}"
printf 'array_task_id=%s\n' "$SLURM_ARRAY_TASK_ID"
printf 'partition=%s\n' "${SLURM_JOB_PARTITION:-unknown}"
printf '%s\n' 'allocation_mode=exclusive'
printf 'slurm_oversubscribe=%s\n' "${PASCAL_SLURM_OVERSUBSCRIBE:-unknown}"
printf '%s\n' 'gurobi_time_limit_seconds=28800'

"$PYTHON_BIN" scripts/run_gurobi_hard_default_8h_shard.py \
    --config "$CONFIG_FILE" \
    --campaign-root "$CAMPAIGN_ROOT" \
    --array-index "$SLURM_ARRAY_TASK_ID"
