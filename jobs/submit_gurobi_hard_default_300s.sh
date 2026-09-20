InvalidOperation: 
Line |
   2 |  [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); Ge .
     |  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
     | Cannot create type. Only core types are supported in this language mode.
#!/bin/bash
# Submit the configuration-sharded 300-second Gurobi validation campaign.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${1:-experiments/gurobi-hard-default-300s.yaml}"
LICENSE_FILE="${GRB_LICENSE_FILE:-$PROJECT_ROOT/secret/gurobi.lic}"
ARRAY_CONCURRENCY="${PASCAL_ARRAY_CONCURRENCY:-3}"
SLURM_TIME="${PASCAL_SHARD_SLURM_TIME:-01:00:00}"
CAMPAIGN_TAG="${PASCAL_CAMPAIGN_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
CAMPAIGN_ROOT="${PASCAL_CAMPAIGN_ROOT:-$PROJECT_ROOT/resultados_finais/gurobi_hard_default_300s_$CAMPAIGN_TAG}"

cd "$PROJECT_ROOT"

for program in git sbatch python; do
    if ! command -v "$program" >/dev/null 2>&1; then
        printf 'submission_error=program_not_available program=%s\n' "$program" >&2
        exit 20
    fi
done
if [[ ! -s "$CONFIG_FILE" ]]; then
    printf 'submission_error=configuration_missing_or_empty path=%s\n' \
        "$CONFIG_FILE" >&2
    exit 21
fi
if [[ ! -s "$LICENSE_FILE" ]]; then
    printf 'submission_error=gurobi_license_missing_or_empty path=%s\n' \
        "$LICENSE_FILE" >&2
    exit 21
fi
if [[ ! "$ARRAY_CONCURRENCY" =~ ^[1-9][0-9]*$ ]]; then
    printf 'submission_error=invalid_array_concurrency value=%s\n' \
        "$ARRAY_CONCURRENCY" >&2
    exit 21
fi
if [[ -e "$CAMPAIGN_ROOT" ]]; then
    printf 'submission_error=campaign_root_already_exists path=%s\n' \
        "$CAMPAIGN_ROOT" >&2
    exit 21
fi

SOURCE_COMMIT="$(git rev-parse --verify HEAD)"
SOURCE_BRANCH="$(git branch --show-current)"
TRACKED_STATUS="$(git status --porcelain --untracked-files=no)"
PYTHON_BIN="$(command -v python)"
if [[ -n "$TRACKED_STATUS" ]]; then
    printf 'submission_error=tracked_worktree_not_clean\n%s\n' \
        "$TRACKED_STATUS" >&2
    exit 22
fi

python scripts/run_gurobi_hard_default_300s_shard.py \
    --config "$CONFIG_FILE" --check-inputs >&2

printf 'source_commit=%s\n' "$SOURCE_COMMIT" >&2
printf 'source_branch=%s\n' "${SOURCE_BRANCH:-detached}" >&2
printf '%s\n' 'source_tracked_clean=true' >&2
printf 'python=%s\n' "$PYTHON_BIN" >&2
printf 'config=%s\n' "$CONFIG_FILE" >&2
printf 'campaign_root=%s\n' "$CAMPAIGN_ROOT" >&2
printf 'array=0-14%%%s\n' "$ARRAY_CONCURRENCY" >&2
printf 'shard_slurm_time=%s\n' "$SLURM_TIME" >&2
printf '%s\n' 'allocation_mode=exclusive' >&2
printf '%s\n' 'gurobi_time_limit_seconds=300' >&2

unset SBATCH_EXCLUSIVE SBATCH_OVERSUBSCRIBE

submit_result="$(sbatch --parsable \
    --exclusive \
    --array="0-14%$ARRAY_CONCURRENCY" \
    --time="$SLURM_TIME" \
    --export="ALL,PASCAL_PYTHON_BIN=$PYTHON_BIN,PASCAL_EXPERIMENT_CONFIG=$CONFIG_FILE,PASCAL_CAMPAIGN_ROOT=$CAMPAIGN_ROOT,PASCAL_SOURCE_COMMIT=$SOURCE_COMMIT,PASCAL_SOURCE_BRANCH=${SOURCE_BRANCH:-detached},PASCAL_SOURCE_TRACKED_CLEAN=true" \
    jobs/run_gurobi_hard_default_300s.slurm)"
job_id="${submit_result%%;*}"
mkdir -p "$CAMPAIGN_ROOT"
{
    printf 'job_id=%s\n' "$job_id"
    printf 'source_commit=%s\n' "$SOURCE_COMMIT"
    printf 'source_branch=%s\n' "${SOURCE_BRANCH:-detached}"
    printf 'config=%s\n' "$CONFIG_FILE"
    printf 'campaign_root=%s\n' "$CAMPAIGN_ROOT"
    printf 'array=0-14%%%s\n' "$ARRAY_CONCURRENCY"
    printf 'shard_slurm_time=%s\n' "$SLURM_TIME"
    printf '%s\n' 'allocation_mode=exclusive'
    printf '%s\n' 'gurobi_time_limit_seconds=300'
} >"$CAMPAIGN_ROOT/submission.txt"
printf 'submission_receipt=%s\n' "$CAMPAIGN_ROOT/submission.txt" >&2
printf '%s\n' "$submit_result"

