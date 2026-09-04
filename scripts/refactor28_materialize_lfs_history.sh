#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

ROOT="$PROJECT_ROOT/.refactor28-lfs-history"
WORK="$ROOT/work"
REPORT="$PROJECT_ROOT/refactor28_lfs_history_report.txt"
CANDIDATES="$PROJECT_ROOT/refactor28_lfs_history_candidates.txt"
TOOL="$PROJECT_ROOT/.refactor28-upstream-history/pyinstxtractor-ng"
TOOL_URL="https://github.com/pyinstxtractor/pyinstxtractor-ng/releases/download/2026.07.03/pyinstxtractor-ng"
TOOL_SHA256="fe51aa23e122133163de873a430b2b88dac182d5519ef348b27890b0fcb4cd27"
GITLAB_ARCHIVE_API="https://gitlab.com/api/v4/projects/lappsufrn%2Fpascal-releases/repository/archive.tar.gz"

# commit|expected LFS oid sha256|declared LFS size|date/description
CASES=(
  "a1e291aa0136df5a38c68a2833791abea7d838bf|dca51522320a35eff4b071d13a433e3586ebb1f9338e6fefe85381f1c94ce65e|20927368|2023-01-17 update binary"
  "af9789aab79ee3952b15b621c41f7eac29166cc0|a51beb414fc3b102b8bdede9c1ed945f633b021df6cd553683e89b52ba829f80|14058008|2022-10-05 update pascal binary"
  "052c00075ae9c8590f8dac8c89e4f81cdfd7915d|3aaf1cdc6802ff41990ffc18a966bc4cbe691fc964887ae9fa81abbb0f4cd912|11765632|2022-04-21 use superpc compiled ver"
  "77afc182e058f7000f6f81ee1d086a1d248edbb8|da3b0b2910c9269d9bd3c8bcc26c5ef87bc0c23405294c7ffb9bef555145ff9f|14777184|2022-04-21 add binary files and install scripts"
)

mkdir -p "$ROOT" "$WORK"
: > "$REPORT"
: > "$CANDIDATES"

log() {
  printf '%s\n' "$*" | tee -a "$REPORT"
}

log "=== PREPARE STANDALONE EXTRACTOR ==="
if [[ ! -x "$TOOL" ]]; then
  mkdir -p "$(dirname "$TOOL")"
  curl -L --fail --retry 3 -o "$TOOL" "$TOOL_URL"
  chmod 700 "$TOOL"
fi
actual_tool_sha="$(sha256sum "$TOOL" | awk '{print $1}')"
log "extractor_sha256=$actual_tool_sha"
if [[ "$actual_tool_sha" != "$TOOL_SHA256" ]]; then
  log "extractor_sha256_mismatch=true"
  exit 3
fi

materialized_count=0
integrity_failure_count=0
candidate_count=0

log "=== MATERIALIZE HISTORICAL LFS ANALYZERS ==="
for entry in "${CASES[@]}"; do
  IFS='|' read -r commit expected_sha expected_size meta <<< "$entry"
  short="${commit:0:12}"
  case_dir="$WORK/$short"
  archive="$case_dir/archive.tar.gz"
  unpack="$case_dir/unpack"
  analysis="$case_dir/analysis"
  rm -rf "$case_dir"
  mkdir -p "$unpack" "$analysis"

  log "--- commit=$commit expected_sha256=$expected_sha expected_size=$expected_size meta=$meta ---"

  url="${GITLAB_ARCHIVE_API}?sha=${commit}&path=bin&include_lfs_blobs=true"
  set +e
  curl -L --fail --retry 3 --silent --show-error -o "$archive" "$url"
  download_rc=$?
  set -e
  log "download_rc=$download_rc"
  if [[ $download_rc -ne 0 ]]; then
    log "materialized=false"
    continue
  fi

  set +e
  tar -xzf "$archive" -C "$unpack"
  tar_rc=$?
  set -e
  log "archive_extract_rc=$tar_rc"
  if [[ $tar_rc -ne 0 ]]; then
    log "materialized=false"
    continue
  fi

  analyzer="$(find "$unpack" -type f -path '*/bin/pascalanalyzer' -print -quit)"
  if [[ -z "$analyzer" || ! -f "$analyzer" ]]; then
    log "analyzer_missing_in_archive=true"
    continue
  fi

  actual_sha="$(sha256sum "$analyzer" | awk '{print $1}')"
  actual_size="$(stat -c '%s' "$analyzer")"
  log "materialized_analyzer=$analyzer"
  log "actual_sha256=$actual_sha"
  log "actual_size=$actual_size"

  sha_ok=false
  size_ok=false
  [[ "$actual_sha" == "$expected_sha" ]] && sha_ok=true
  [[ "$actual_size" == "$expected_size" ]] && size_ok=true
  log "lfs_sha256_verified=$sha_ok"
  log "lfs_size_verified=$size_ok"

  if [[ "$sha_ok" != true || "$size_ok" != true ]]; then
    integrity_failure_count=$((integrity_failure_count + 1))
    log "analysis_status=integrity_failure"
    continue
  fi

  materialized_count=$((materialized_count + 1))
  log "analysis_status=materialized_verified"
  file "$analyzer" | tee -a "$REPORT"

  outer_matches="$analysis/outer_matches.txt"
  strings -a -n 3 "$analyzer" 2>/dev/null \
    | grep -aEi 'region_energy|raplpackage|raplcorepackage|performance_features|profiler|perfmon|RAPL_ENERGY|SYSTEMWIDE' \
    > "$outer_matches" || true
  log "outer_string_matches=$(wc -l < "$outer_matches")"

  extract_dir="$analysis/extract"
  mkdir -p "$extract_dir"
  cp "$analyzer" "$extract_dir/pascalanalyzer"
  chmod 700 "$extract_dir/pascalanalyzer"
  set +e
  (
    cd "$extract_dir"
    "$TOOL" pascalanalyzer > extract.log 2>&1
  )
  pyinst_rc=$?
  set -e
  log "pyinstaller_extract_rc=$pyinst_rc"

  extracted_matches="$analysis/extracted_matches.txt"
  : > "$extracted_matches"
  if [[ $pyinst_rc -eq 0 && -d "$extract_dir/pascalanalyzer_extracted" ]]; then
    while IFS= read -r -d '' path; do
      strings -a -n 3 "$path" 2>/dev/null \
        | grep -aEi 'region_energy|raplpackage|raplcorepackage|performance_features|profiler|perfmon|RAPL_ENERGY|SYSTEMWIDE' \
        | sed "s#^#$path:#" \
        >> "$extracted_matches" || true
    done < <(find "$extract_dir/pascalanalyzer_extracted" -type f -print0)
  fi

  combined="$analysis/combined_matches.txt"
  cat "$outer_matches" "$extracted_matches" > "$combined"

  region_energy=false
  rapl_domains=false
  profiler=false
  performance_features=false
  systemwide=false
  rapl_energy=false

  grep -aEiq 'region_energy' "$combined" && region_energy=true || true
  grep -aEiq 'raplpackage|raplcorepackage' "$combined" && rapl_domains=true || true
  grep -aEiq '(^|[^[:alnum:]_])profiler([^[:alnum:]_]|$)' "$combined" && profiler=true || true
  grep -aEiq 'performance_features|perfmon' "$combined" && performance_features=true || true
  grep -aEiq 'SYSTEMWIDE' "$combined" && systemwide=true || true
  grep -aEiq 'RAPL_ENERGY' "$combined" && rapl_energy=true || true

  log "region_energy_present=$region_energy"
  log "rapl_domain_names_present=$rapl_domains"
  log "profiler_reference_present=$profiler"
  log "performance_features_reference_present=$performance_features"
  log "SYSTEMWIDE_reference_present=$systemwide"
  log "RAPL_ENERGY_reference_present=$rapl_energy"

  if [[ "$region_energy" == true || "$rapl_domains" == true ]]; then
    candidate_count=$((candidate_count + 1))
    printf '%s|%s|%s|region_energy=%s|rapl_domains=%s|profiler=%s|performance_features=%s|SYSTEMWIDE=%s|RAPL_ENERGY=%s\n' \
      "$commit" "$actual_sha" "$meta" "$region_energy" "$rapl_domains" "$profiler" "$performance_features" "$systemwide" "$rapl_energy" \
      | tee -a "$CANDIDATES" "$REPORT"
  fi
done

log "=== CLASSIFICATION ==="
log "historical_lfs_expected_count=${#CASES[@]}"
log "historical_lfs_materialized_count=$materialized_count"
log "historical_lfs_integrity_failure_count=$integrity_failure_count"
log "viewer_energy_candidate_count=$candidate_count"
log "candidates=$CANDIDATES"
if [[ $candidate_count -gt 0 ]]; then
  log "historical_viewer_energy_candidate_found=true"
elif [[ $materialized_count -eq ${#CASES[@]} && $integrity_failure_count -eq 0 ]]; then
  log "historical_viewer_energy_candidate_found=false"
else
  log "historical_viewer_energy_candidate_found=inconclusive"
fi
log "report=$REPORT"
log "=== HISTORICAL LFS MATERIALIZATION COMPLETED ==="
