#!/bin/bash
set -e

exec python3 "$SLURM_SUBMIT_DIR/scripts/smoke_pascal_region.py"
