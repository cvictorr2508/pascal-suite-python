#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${PASCAL_RELEASE_COMPARE_DIR:-$REPO_ROOT/.refactor28-release-current}"
ARCHIVE="$WORK_DIR/pascal-releases-master.zip"
EXTRACT_DIR="$WORK_DIR/extracted"
URL="https://gitlab.com/lappsufrn/pascal-releases/-/archive/master/pascal-releases-master.zip"
INSTALLED_ANALYZER="${PASCAL_ANALYZER_INSTALLED:-/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/bin/pascalanalyzer}"

mkdir -p "$WORK_DIR"
rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"

printf '%s\n' '=== DOWNLOAD OFFICIAL MASTER RELEASE ==='
printf 'url=%s\n' "$URL"
if command -v wget >/dev/null 2>&1; then
  wget -q -O "$ARCHIVE" "$URL"
elif command -v curl >/dev/null 2>&1; then
  curl -fsSL "$URL" -o "$ARCHIVE"
else
  printf '%s\n' 'ERROR: wget/curl unavailable'
  exit 2
fi

unzip -q "$ARCHIVE" -d "$EXTRACT_DIR"
RELEASE_ROOT="$(find "$EXTRACT_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [[ -z "$RELEASE_ROOT" ]]; then
  printf '%s\n' 'ERROR: release root not found'
  exit 3
fi
printf 'release_root=%s\n' "$RELEASE_ROOT"

printf '%s\n' '=== RELEASE TREE: PROFILER CANDIDATES ==='
find "$RELEASE_ROOT" -type f \( -iname 'profiler.py' -o -iname '*profiler*' \) -print | sort || true

printf '%s\n' '=== RELEASE TREE: TEXT REFERENCES ==='
grep -RIl --exclude='pascalanalyzer' -E '(^|[^[:alnum:]_])import[[:space:]]+profiler|from[[:space:]]+profiler|region_energy|raplpackage|raplcorepackage|rapl-perf|rapl_sample-perf' "$RELEASE_ROOT" 2>/dev/null | sort || true

RELEASE_ANALYZER="$(find "$RELEASE_ROOT" -type f -name pascalanalyzer -perm -u+x | head -n 1)"
if [[ -z "$RELEASE_ANALYZER" ]]; then
  RELEASE_ANALYZER="$(find "$RELEASE_ROOT" -type f -name pascalanalyzer | head -n 1)"
fi

printf '%s\n' '=== ANALYZER COMPARISON ==='
printf 'installed_analyzer=%s\n' "$INSTALLED_ANALYZER"
printf 'release_analyzer=%s\n' "${RELEASE_ANALYZER:-<missing>}"

if [[ -f "$INSTALLED_ANALYZER" ]]; then
  file "$INSTALLED_ANALYZER" || true
  sha256sum "$INSTALLED_ANALYZER" || true
fi

if [[ -n "$RELEASE_ANALYZER" && -f "$RELEASE_ANALYZER" ]]; then
  file "$RELEASE_ANALYZER" || true
  sha256sum "$RELEASE_ANALYZER" || true
  if cmp -s "$INSTALLED_ANALYZER" "$RELEASE_ANALYZER"; then
    printf '%s\n' 'analyzer_binary_identical=true'
  else
    printf '%s\n' 'analyzer_binary_identical=false'
  fi
else
  printf '%s\n' 'release_analyzer_missing=true'
fi

printf '%s\n' '=== INSTALLED ANALYZER STRINGS ==='
strings "$INSTALLED_ANALYZER" 2>/dev/null | grep -Ei 'profiler|region_energy|raplpackage|raplcorepackage|rapl-perf|rapl_sample-perf|_MEIPASS|PYZ-00' | sort -u || true

if [[ -n "$RELEASE_ANALYZER" && -f "$RELEASE_ANALYZER" ]]; then
  printf '%s\n' '=== RELEASE ANALYZER STRINGS ==='
  strings "$RELEASE_ANALYZER" 2>/dev/null | grep -Ei 'profiler|region_energy|raplpackage|raplcorepackage|rapl-perf|rapl_sample-perf|_MEIPASS|PYZ-00' | sort -u || true
fi

printf '%s\n' '=== RELEASE ENVIRONMENT ==='
find "$RELEASE_ROOT" -maxdepth 2 -type f \( -name 'env.sh' -o -name 'requirements*.txt' -o -name 'README*' \) -print | sort || true

if [[ -f "$RELEASE_ROOT/env.sh" ]]; then
  printf '%s\n' '--- env.sh ---'
  sed -n '1,220p' "$RELEASE_ROOT/env.sh"
fi

printf '%s\n' '=== CLASSIFICATION HINTS ==='
if find "$RELEASE_ROOT" -type f \( -iname 'profiler.py' -o -iname '*profiler*' \) | grep -q .; then
  printf '%s\n' 'official_release_contains_profiler_candidate=true'
else
  printf '%s\n' 'official_release_contains_profiler_candidate=false'
fi

if [[ -n "$RELEASE_ANALYZER" && -f "$RELEASE_ANALYZER" ]] && strings "$RELEASE_ANALYZER" 2>/dev/null | grep -q 'region_energy'; then
  printf '%s\n' 'official_release_analyzer_mentions_region_energy=true'
else
  printf '%s\n' 'official_release_analyzer_mentions_region_energy=false'
fi

printf '%s\n' '=== OFFICIAL RELEASE COMPARISON COMPLETED ==='
