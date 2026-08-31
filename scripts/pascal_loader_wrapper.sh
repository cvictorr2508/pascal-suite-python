#!/bin/bash
set -Eeuo pipefail

MODE="${PASCAL_LOADER_MODE:-baseline}"
PASCAL_LIB="${PASCAL_OPS_LIB:-/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/lib/libmpascalops.so}"
PYTHON_BIN="${PASCAL_DIAG_PYTHON:-python3}"
SCRIPT="${SLURM_SUBMIT_DIR:-$(pwd)}/scripts/diagnose_pascal_loader.py"

case "$MODE" in
    baseline)
        unset LD_PRELOAD
        ;;
    preload)
        export LD_PRELOAD="$PASCAL_LIB${LD_PRELOAD:+:$LD_PRELOAD}"
        ;;
    rtld_global)
        unset LD_PRELOAD
        ;;
    *)
        echo "Unknown PASCAL_LOADER_MODE=$MODE" >&2
        exit 2
        ;;
esac

exec "$PYTHON_BIN" "$SCRIPT"
