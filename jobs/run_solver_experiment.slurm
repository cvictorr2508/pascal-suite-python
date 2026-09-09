#!/bin/bash
#SBATCH --job-name=solver_matrix
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --partition=intel-128
#SBATCH --output=solver_matrix_%j.out
#SBATCH --error=solver_matrix_%j.err

source /etc/profile
source /etc/profile.d/modules.sh 2>/dev/null || true
set -Eeuo pipefail

module purge
module load softwares/python/3.13.7-gnu8
module load softwares/pascalsuite/2025-07-08

cd "$SLURM_SUBMIT_DIR"

CONFIG_FILE="${PASCAL_EXPERIMENT_CONFIG:-experiments/gurobi-profile-smoke.yaml}"
LICENSE_FILE="${GRB_LICENSE_FILE:-$SLURM_SUBMIT_DIR/secret/gurobi.lic}"
PYTHON_BIN="${PASCAL_PYTHON_BIN:-$(command -v python || true)}"
SOURCE_COMMIT="${PASCAL_SOURCE_COMMIT:-}"
SOURCE_BRANCH="${PASCAL_SOURCE_BRANCH:-detached}"
SOURCE_TRACKED_CLEAN="${PASCAL_SOURCE_TRACKED_CLEAN:-}"
ALLOCATION_MODE="${PASCAL_SLURM_ALLOCATION_MODE:-}"
SCHEDULER_OVERSUBSCRIBE=""
SCHEDULER_EXCLUSIVE=""

require_file() {
    local path="$1"
    local label="$2"
    if [[ ! -s "$path" ]]; then
        printf 'preflight_error=%s path=%s\n' "$label" "$path" >&2
        exit 11
    fi
}

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
    printf 'preflight_error=python_not_available_on_path\n' >&2
    exit 10
fi
if ! command -v pascalanalyzer >/dev/null 2>&1; then
    printf 'preflight_error=pascalanalyzer_not_available_on_path\n' >&2
    exit 10
fi
if [[ ! "$SOURCE_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]]; then
    printf 'preflight_error=source_commit_missing_or_invalid value=%s\n' \
        "$SOURCE_COMMIT" >&2
    exit 12
fi
if [[ "$SOURCE_TRACKED_CLEAN" != "true" ]]; then
    printf 'preflight_error=tracked_worktree_not_clean value=%s\n' \
        "$SOURCE_TRACKED_CLEAN" >&2
    exit 12
fi
if [[ "$ALLOCATION_MODE" != "exclusive" && "$ALLOCATION_MODE" != "shared" ]]; then
    printf 'preflight_error=invalid_allocation_mode value=%s\n' \
        "$ALLOCATION_MODE" >&2
    exit 12
fi

require_file "$CONFIG_FILE" "configuration_missing_or_empty"
SOLVER="$(
    "$PYTHON_BIN" - "$CONFIG_FILE" <<'PY'
import sys
from pathlib import Path

import yaml

with Path(sys.argv[1]).open("r", encoding="utf-8") as stream:
    document = yaml.safe_load(stream)
print(document["experiment"]["solver"])
PY
)"

case "$SOLVER" in
    gurobi)
        require_file "$LICENSE_FILE" "gurobi_license_missing_or_empty"
        export GRB_LICENSE_FILE="$LICENSE_FILE"
        ;;
    scip)
        if ! "$PYTHON_BIN" -c 'import pyscipopt' >/dev/null 2>&1; then
            printf 'preflight_error=pyscipopt_not_available\n' >&2
            exit 10
        fi
        ;;
    *)
        printf 'preflight_error=unsupported_solver value=%s\n' "$SOLVER" >&2
        exit 12
        ;;
esac

job_field() {
    local field="$1"
    printf '%s\n' "$SCHEDULER_JOB_RECORD" |
        tr ' ' '\n' |
        awk -F= -v requested="$field" \
            '$1 == requested { print $2; exit }'
}

if command -v scontrol >/dev/null 2>&1; then
    SCHEDULER_JOB_RECORD="$(
        scontrol show job -o "$SLURM_JOB_ID" 2>/dev/null || true
    )"
    SCHEDULER_OVERSUBSCRIBE="$(job_field "OverSubscribe")"
    if [[ -z "$SCHEDULER_OVERSUBSCRIBE" ]]; then
        SCHEDULER_OVERSUBSCRIBE="$(job_field "Shared")"
    fi
    SCHEDULER_EXCLUSIVE="$(job_field "Exclusive")"
fi

export PASCAL_SOURCE_COMMIT="$SOURCE_COMMIT"
export PASCAL_SOURCE_BRANCH="$SOURCE_BRANCH"
export PASCAL_SOURCE_TRACKED_CLEAN="$SOURCE_TRACKED_CLEAN"
export PASCAL_SLURM_ALLOCATION_MODE="$ALLOCATION_MODE"
export PASCAL_SLURM_OVERSUBSCRIBE="$SCHEDULER_OVERSUBSCRIBE"
export PASCAL_SLURM_EXCLUSIVE="$SCHEDULER_EXCLUSIVE"

printf 'host=%s\n' "$(hostname -f)"
printf 'python=%s\n' "$PYTHON_BIN"
printf 'python_version=%s\n' "$("$PYTHON_BIN" --version 2>&1)"
printf 'source_commit=%s\n' "$SOURCE_COMMIT"
printf 'source_branch=%s\n' "$SOURCE_BRANCH"
printf 'source_tracked_clean=%s\n' "$SOURCE_TRACKED_CLEAN"
printf 'config=%s\n' "$CONFIG_FILE"
printf 'solver=%s\n' "$SOLVER"
printf 'partition=%s\n' "${SLURM_JOB_PARTITION:-unknown}"
printf 'allocation_mode=%s\n' "$ALLOCATION_MODE"
printf 'slurm_oversubscribe=%s\n' "${SCHEDULER_OVERSUBSCRIBE:-unknown}"
printf 'slurm_exclusive=%s\n' "${SCHEDULER_EXCLUSIVE:-unknown}"

"$PYTHON_BIN" rodar_yaml.py "$CONFIG_FILE"
