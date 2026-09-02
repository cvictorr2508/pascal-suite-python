#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PASCAL_ANALYZER="${PASCAL_ANALYZER:-/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/bin/pascalanalyzer}"
TOOLS_ROOT="$PROJECT_ROOT/.refactor28-pyi-tools"
EXTRACT_ROOT="$PROJECT_ROOT/.refactor28-pyi-extracted"
LISTING="$PROJECT_ROOT/refactor28_pyinstaller_archive_listing.txt"
MATCHES="$PROJECT_ROOT/refactor28_pyinstaller_archive_matches.txt"
STRINGS_MATCHES="$PROJECT_ROOT/refactor28_pyinstaller_string_matches.txt"
EXTRACT_LOG="$PROJECT_ROOT/refactor28_pyinstxtractor.log"

TOOL_VERSION="2026.07.03"
TOOL_URL="https://github.com/pyinstxtractor/pyinstxtractor-ng/releases/download/${TOOL_VERSION}/pyinstxtractor-ng"
TOOL_SHA256="fe51aa23e122133163de873a430b2b88dac182d5519ef348b27890b0fcb4cd27"
TOOL="$TOOLS_ROOT/pyinstxtractor-ng"

if [[ ! -x "$PASCAL_ANALYZER" ]]; then
    echo "analyzer_missing=$PASCAL_ANALYZER" >&2
    exit 2
fi

mkdir -p "$TOOLS_ROOT"

if [[ ! -f "$TOOL" ]]; then
    echo "=== DOWNLOAD PYINSTXTRACTOR-NG ==="
    echo "tool_version=$TOOL_VERSION"
    echo "tool_url=$TOOL_URL"
    if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 3 --connect-timeout 20 "$TOOL_URL" -o "$TOOL"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$TOOL" "$TOOL_URL"
    else
        echo "download_tool_missing=curl_or_wget" >&2
        exit 3
    fi
fi

actual_tool_sha="$(sha256sum "$TOOL" | awk '{print $1}')"
echo "tool_sha256=$actual_tool_sha"
if [[ "$actual_tool_sha" != "$TOOL_SHA256" ]]; then
    echo "tool_sha256_mismatch_expected=$TOOL_SHA256" >&2
    exit 4
fi
chmod 700 "$TOOL"

echo "=== ANALYZER ==="
echo "analyzer=$PASCAL_ANALYZER"
sha256sum "$PASCAL_ANALYZER"
file "$PASCAL_ANALYZER"

echo "=== EXTRACTOR ==="
"$TOOL" --help | sed -n '1,20p' || true

rm -rf "$EXTRACT_ROOT"
mkdir -p "$EXTRACT_ROOT"
cp "$PASCAL_ANALYZER" "$EXTRACT_ROOT/pascalanalyzer"

set +e
(
    cd "$EXTRACT_ROOT"
    "$TOOL" pascalanalyzer
) >"$EXTRACT_LOG" 2>&1
extract_rc=$?
set -e

echo "extract_rc=$extract_rc"
echo "extract_log=$EXTRACT_LOG"
cat "$EXTRACT_LOG"

if [[ $extract_rc -ne 0 ]]; then
    echo "archive_extraction_failed=true" >&2
    exit 5
fi

EXTRACTED_DIR="$EXTRACT_ROOT/pascalanalyzer_extracted"
if [[ ! -d "$EXTRACTED_DIR" ]]; then
    echo "extracted_dir_missing=$EXTRACTED_DIR" >&2
    exit 6
fi

find "$EXTRACTED_DIR" -type f -printf '%P\n' | LC_ALL=C sort > "$LISTING"
{
    grep -Ei '(^|[^[:alnum:]_])(profiler|rapl|perf|sensor|energy)([^[:alnum:]_]|$)' "$LISTING" || true
} > "$MATCHES"

echo "=== RELEVANT ARCHIVE MEMBERS ==="
cat "$MATCHES"

{
    grep -aRniE 'region_energy|profiler|raplpackage|raplcorepackage|rapl[_-]?perf|rapl_sample[_-]?perf' "$EXTRACTED_DIR" 2>/dev/null || true
} > "$STRINGS_MATCHES"

echo "=== RELEVANT BYTECODE/STRING MATCHES ==="
cat "$STRINGS_MATCHES"

echo "=== CLASSIFICATION ==="
if grep -Eiq '(^|[./[:space:]_-])profiler([./[:space:]_-]|$)' "$LISTING"; then
    echo "profiler_archive_member_present=true"
else
    echo "profiler_archive_member_present=false"
fi

if grep -Eiq 'rapl' "$LISTING"; then
    echo "rapl_archive_member_present=true"
else
    echo "rapl_archive_member_present=false"
fi

if grep -Eiq 'perf' "$LISTING"; then
    echo "perf_archive_member_present=true"
else
    echo "perf_archive_member_present=false"
fi

if grep -Eiq 'sensor' "$LISTING"; then
    echo "sensor_archive_member_present=true"
else
    echo "sensor_archive_member_present=false"
fi

if grep -aEiq 'region_energy' "$STRINGS_MATCHES"; then
    echo "region_energy_string_present=true"
else
    echo "region_energy_string_present=false"
fi

if grep -aEiq 'profiler' "$STRINGS_MATCHES"; then
    echo "profiler_string_present=true"
else
    echo "profiler_string_present=false"
fi

echo "listing=$LISTING"
echo "matches=$MATCHES"
echo "string_matches=$STRINGS_MATCHES"
echo "=== PYINSTALLER ARCHIVE INSPECTION COMPLETED ==="
