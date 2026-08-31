#!/usr/bin/env python3

import ctypes
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

PASCAL_LIB = os.environ.get(
    "PASCAL_OPS_LIB",
    "/opt/npad/shared/softwares/pascalsuite/pascal-suite-2025-07-08/lib/libmpascalops.so",
)
LOADER_MODE = os.environ.get("PASCAL_LOADER_MODE", "baseline")


def _library_maps() -> list[str]:
    maps_path = Path("/proc/self/maps")
    if not maps_path.exists():
        return []
    return [
        line.strip()
        for line in maps_path.read_text(encoding="utf-8").splitlines()
        if "libmpascalops" in line
    ]


preopen_status = {
    "requested": LOADER_MODE == "rtld_global",
    "success": False,
    "error": None,
}
_preopened_library = None

if LOADER_MODE == "rtld_global":
    try:
        _preopened_library = ctypes.CDLL(PASCAL_LIB, mode=ctypes.RTLD_GLOBAL)
        preopen_status["success"] = True
    except Exception as exc:  # diagnostic path: preserve exact loader error
        preopen_status["error"] = repr(exc)

from pascalpy.instrumentation.pascalops import (  # noqa: E402
    instrumentation_status,
    pascal_region,
)


def main() -> int:
    before = {
        "pid": os.getpid(),
        "loader_mode": LOADER_MODE,
        "ld_preload": os.environ.get("LD_PRELOAD"),
        "pascal_library": PASCAL_LIB,
        "rtld_global_preopen": preopen_status,
        "maps": _library_maps(),
        "instrumentation_status": instrumentation_status(),
    }

    print("=== PASCAL LOADER DIAGNOSTIC ===", flush=True)
    print(json.dumps(before, indent=2, sort_keys=True), flush=True)
    print("ANTES DA REGIAO PYTHON", flush=True)

    started = time.perf_counter()
    with pascal_region(
        1,
        filename=Path(__file__).name,
        start_line=100,
        stop_line=110,
    ):
        deadline = time.perf_counter() + 2.0
        value = 1
        while time.perf_counter() < deadline:
            value = (value * 1664525 + 1013904223) & 0xFFFFFFFF
    stopped = time.perf_counter()

    after = {
        "elapsed_region_wall_s": stopped - started,
        "maps": _library_maps(),
        "value": value,
    }

    print("DEPOIS DA REGIAO PYTHON", flush=True)
    print(json.dumps(after, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
