#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PASCAL_ANALYZER="${PASCAL_ANALYZER:-/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/bin/pascalanalyzer}"
TOOLS_ROOT="$PROJECT_ROOT/.refactor28-pyi-tools"
VENV="$TOOLS_ROOT/venv"
LISTING="$PROJECT_ROOT/refactor28_pyinstaller_archive_listing.txt"
MATCHES="$PROJECT_ROOT/refactor28_pyinstaller_archive_matches.txt"
REQUIREMENT='pyinstaller>=6.10,<7'
PUBLIC_PYPI='https://pypi.org/simple'

if [[ ! -x "$PASCAL_ANALYZER" ]]; then
    echo "analyzer_missing=$PASCAL_ANALYZER" >&2
    exit 2
fi

mkdir -p "$TOOLS_ROOT"

if [[ ! -x "$VENV/bin/python" ]]; then
    python3 -m venv "$VENV"
fi

ARCHIVE_VIEWER="$VENV/bin/pyi-archive_viewer"

if [[ ! -x "$ARCHIVE_VIEWER" ]]; then
    echo "=== INSTALL PYINSTALLER TOOL ==="
    echo "requirement=$REQUIREMENT"

    set +e
    "$VENV/bin/python" -m pip install \
        --disable-pip-version-check \
        --quiet \
        "$REQUIREMENT"
    install_rc=$?
    set -e

    if [[ $install_rc -ne 0 ]]; then
        echo "default_index_install_failed=true"
        echo "retry_index=$PUBLIC_PYPI"
        "$VENV/bin/python" -m pip install \
            --disable-pip-version-check \
            --quiet \
            --index-url "$PUBLIC_PYPI" \
            "$REQUIREMENT"
    fi
fi

if [[ ! -x "$ARCHIVE_VIEWER" ]]; then
    echo "pyi_archive_viewer_missing=$ARCHIVE_VIEWER" >&2
    exit 3
fi

echo "=== ANALYZER ==="
echo "analyzer=$PASCAL_ANALYZER"
sha256sum "$PASCAL_ANALYZER"
file "$PASCAL_ANALYZER"

echo "=== PYINSTALLER TOOL ==="
"$VENV/bin/python" - <<'PY'
import sys
import PyInstaller
print("python_version=", sys.version.replace("\n", " "))
print("pyinstaller_version=", PyInstaller.__version__)
PY

echo "=== RECURSIVE ARCHIVE LISTING ==="
"$ARCHIVE_VIEWER" -l -r "$PASCAL_ANALYZER" > "$LISTING"
echo "listing=$LISTING"
wc -l "$LISTING"

{
    grep -Ei '(^|[^[:alnum:]_])(profiler|rapl|perf|sensor|energy)([^[:alnum:]_]|$)' "$LISTING" || true
} > "$MATCHES"

echo "=== RELEVANT ARCHIVE MEMBERS ==="
cat "$MATCHES"

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

echo "=== NOTE ==="
echo "Archive member names can prove whether a module is bundled, but they do not prove whether string literals such as region_energy exist inside compressed bytecode."
echo "=== PYINSTALLER ARCHIVE INSPECTION COMPLETED ==="
