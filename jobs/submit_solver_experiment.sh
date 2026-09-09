#!/bin/bash
# Capture source provenance and allocation policy before entering Slurm.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${1:-experiments/gurobi-profile-smoke.yaml}"
ALLOCATION_MODE="${PASCAL_SLURM_ALLOCATION_MODE:-exclusive}"

case "$ALLOCATION_MODE" in
    exclusive)
        ALLOCATION_ARGUMENTS=(--exclusive)
        ;;
    shared)
        ALLOCATION_ARGUMENTS=(--oversubscribe)
        ;;
    *)
        printf 'submission_error=invalid_allocation_mode value=%s expected=exclusive_or_shared\n' \
            "$ALLOCATION_MODE" >&2
        exit 23
        ;;
esac

cd "$PROJECT_ROOT"

if ! command -v git >/dev/null 2>&1; then
    printf 'submission_error=git_not_available_on_submission_node\n' >&2
    exit 20
fi
if ! command -v sbatch >/dev/null 2>&1; then
    printf 'submission_error=sbatch_not_available\n' >&2
    exit 20
fi
if [[ ! -s "$CONFIG_FILE" ]]; then
    printf 'submission_error=configuration_missing_or_empty path=%s\n' \
        "$CONFIG_FILE" >&2
    exit 21
fi

PYTHON_BIN="$(command -v python || true)"
SOURCE_COMMIT="$(git rev-parse --verify HEAD)"
SOURCE_BRANCH="$(git branch --show-current)"
TRACKED_STATUS="$(git status --porcelain --untracked-files=no)"

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
    printf 'submission_error=python_not_available_on_path\n' >&2
    exit 20
fi
if [[ -n "$TRACKED_STATUS" ]]; then
    printf 'submission_error=tracked_worktree_not_clean\n%s\n' \
        "$TRACKED_STATUS" >&2
    exit 22
fi

printf 'source_commit=%s\n' "$SOURCE_COMMIT" >&2
printf 'source_branch=%s\n' "${SOURCE_BRANCH:-detached}" >&2
printf 'source_tracked_clean=true\n' >&2
printf 'python=%s\n' "$PYTHON_BIN" >&2
printf 'config=%s\n' "$CONFIG_FILE" >&2
printf 'allocation_mode=%s\n' "$ALLOCATION_MODE" >&2

# Prevent inherited SBATCH flag variables from conflicting with the explicit policy.
unset SBATCH_EXCLUSIVE SBATCH_OVERSUBSCRIBE

sbatch --parsable \
    "${ALLOCATION_ARGUMENTS[@]}" \
    --export="ALL,PASCAL_PYTHON_BIN=$PYTHON_BIN,PASCAL_EXPERIMENT_CONFIG=$CONFIG_FILE,PASCAL_SOURCE_COMMIT=$SOURCE_COMMIT,PASCAL_SOURCE_BRANCH=${SOURCE_BRANCH:-detached},PASCAL_SOURCE_TRACKED_CLEAN=true,PASCAL_SLURM_ALLOCATION_MODE=$ALLOCATION_MODE" \
    jobs/run_solver_experiment.slurm
