#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

ROOT="$PROJECT_ROOT/.refactor28-upstream-history"
RELEASES="$ROOT/pascal-releases"
WORK="$ROOT/work"
TOOL="$ROOT/pyinstxtractor-ng"
TOOL_URL="https://github.com/pyinstxtractor/pyinstxtractor-ng/releases/download/2026.07.03/pyinstxtractor-ng"
TOOL_SHA256="fe51aa23e122133163de873a430b2b88dac182d5519ef348b27890b0fcb4cd27"
RELEASES_URL="https://gitlab.com/lappsufrn/pascal-releases.git"
REPORT="$PROJECT_ROOT/refactor28_release_history_report.txt"
CANDIDATES="$PROJECT_ROOT/refactor28_release_history_candidates.txt"

mkdir -p "$ROOT" "$WORK"
: > "$REPORT"
: > "$CANDIDATES"

log() {
    printf '%s\n' "$*" | tee -a "$REPORT"
}

log "=== FETCH PASCAL RELEASE HISTORY ==="
if [[ ! -d "$RELEASES/.git" ]]; then
    git clone "$RELEASES_URL" "$RELEASES" 2>&1 | tee -a "$REPORT"
else
    git -C "$RELEASES" fetch --all --tags --prune 2>&1 | tee -a "$REPORT"
fi

log "repository=$RELEASES"
log "remote=$RELEASES_URL"
log "head=$(git -C "$RELEASES" rev-parse HEAD)"
log "commit_count=$(git -C "$RELEASES" rev-list --all --count)"

log "=== PREPARE STANDALONE EXTRACTOR ==="
if [[ ! -x "$TOOL" ]]; then
    curl -L --fail --retry 3 -o "$TOOL" "$TOOL_URL"
    chmod 700 "$TOOL"
fi
actual_tool_sha="$(sha256sum "$TOOL" | awk '{print $1}')"
log "extractor_sha256=$actual_tool_sha"
if [[ "$actual_tool_sha" != "$TOOL_SHA256" ]]; then
    log "extractor_sha256_mismatch=true"
    exit 3
fi

log "=== ANALYZER CHANGE HISTORY ==="
mapfile -t COMMITS < <(git -C "$RELEASES" log --all --format='%H' -- bin/pascalanalyzer)
log "analyzer_change_commit_count=${#COMMITS[@]}"

if [[ ${#COMMITS[@]} -eq 0 ]]; then
    log "analyzer_history_missing=true"
    exit 4
fi

declare -A SEEN_BLOBS=()
CANDIDATE_COUNT=0
DISTINCT_COUNT=0

for commit in "${COMMITS[@]}"; do
    blob="$(git -C "$RELEASES" rev-parse "$commit:bin/pascalanalyzer" 2>/dev/null || true)"
    [[ -n "$blob" ]] || continue
    if [[ -n "${SEEN_BLOBS[$blob]:-}" ]]; then
        continue
    fi
    SEEN_BLOBS[$blob]=1
    DISTINCT_COUNT=$((DISTINCT_COUNT + 1))

    meta="$(git -C "$RELEASES" show -s --format='%cs|%s' "$commit")"
    short="${commit:0:12}"
    case_dir="$WORK/$short"
    rm -rf "$case_dir"
    mkdir -p "$case_dir"
    analyzer="$case_dir/pascalanalyzer"
    git -C "$RELEASES" show "$commit:bin/pascalanalyzer" > "$analyzer"
    chmod 700 "$analyzer"

    sha="$(sha256sum "$analyzer" | awk '{print $1}')"
    log "--- analyzer commit=$commit blob=$blob sha256=$sha meta=$meta ---"

    tree_matches="$case_dir/tree_matches.txt"
    git -C "$RELEASES" ls-tree -r --name-only "$commit" \
        | grep -aEi 'profiler|performance_features|perfmon|region_energy|raplpackage|raplcorepackage' \
        > "$tree_matches" || true
    if [[ -s "$tree_matches" ]]; then
        log "tree_dependency_candidates=true"
        sed 's/^/tree: /' "$tree_matches" | tee -a "$REPORT"
    else
        log "tree_dependency_candidates=false"
    fi

    outer_matches="$case_dir/outer_strings.txt"
    strings -a "$analyzer" \
        | grep -aEi 'region_energy|raplpackage|raplcorepackage|performance_features|profiler|perfmon|RAPL_ENERGY|SYSTEMWIDE' \
        > "$outer_matches" || true
    log "outer_string_matches=$(wc -l < "$outer_matches")"

    extract_dir="$case_dir/extract"
    mkdir -p "$extract_dir"
    cp "$analyzer" "$extract_dir/pascalanalyzer"
    set +e
    (
        cd "$extract_dir"
        "$TOOL" pascalanalyzer > extract.log 2>&1
    )
    extract_rc=$?
    set -e
    log "extract_rc=$extract_rc"

    extracted_matches="$case_dir/extracted_matches.txt"
    : > "$extracted_matches"
    if [[ $extract_rc -eq 0 && -d "$extract_dir/pascalanalyzer_extracted" ]]; then
        while IFS= read -r -d '' path; do
            strings -a -n 3 "$path" 2>/dev/null \
                | grep -aEi 'region_energy|raplpackage|raplcorepackage|performance_features|profiler|perfmon|RAPL_ENERGY|SYSTEMWIDE' \
                | sed "s#^#$path:#" \
                >> "$extracted_matches" || true
        done < <(find "$extract_dir/pascalanalyzer_extracted" -type f -print0)
    fi

    region_energy=false
    rapl_domains=false
    profiler=false
    performance_features=false

    if grep -aEiq 'region_energy' "$extracted_matches"; then region_energy=true; fi
    if grep -aEiq 'raplpackage|raplcorepackage' "$extracted_matches"; then rapl_domains=true; fi
    if grep -aEiq '(^|[^[:alnum:]_])profiler([^[:alnum:]_]|$)' "$extracted_matches" || grep -aEiq 'profiler' "$tree_matches"; then profiler=true; fi
    if grep -aEiq 'performance_features|perfmon' "$extracted_matches" || grep -aEiq 'performance_features|perfmon' "$tree_matches"; then performance_features=true; fi

    log "region_energy_present=$region_energy"
    log "rapl_domain_names_present=$rapl_domains"
    log "profiler_dependency_present=$profiler"
    log "performance_features_dependency_present=$performance_features"

    if [[ "$region_energy" == true || "$rapl_domains" == true ]]; then
        CANDIDATE_COUNT=$((CANDIDATE_COUNT + 1))
        printf '%s|%s|%s|region_energy=%s|rapl_domains=%s|profiler=%s|performance_features=%s\n' \
            "$commit" "$sha" "$meta" "$region_energy" "$rapl_domains" "$profiler" "$performance_features" \
            | tee -a "$CANDIDATES" "$REPORT"
    fi

done

log "=== CLASSIFICATION ==="
log "distinct_analyzer_binaries=$DISTINCT_COUNT"
log "viewer_energy_candidate_count=$CANDIDATE_COUNT"
log "candidates=$CANDIDATES"
if [[ $CANDIDATE_COUNT -gt 0 ]]; then
    log "historical_viewer_energy_candidate_found=true"
else
    log "historical_viewer_energy_candidate_found=false"
fi
log "report=$REPORT"
log "=== RELEASE HISTORY PROBE COMPLETED ==="
