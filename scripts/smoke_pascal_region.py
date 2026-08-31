#!/usr/bin/env python3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.instrumentation.pascalops import (  # noqa: E402
    instrumentation_status,
    pascal_region,
)


def main() -> int:
    print("=== SMOKE PASCAL REGION ===")
    print(instrumentation_status())
    print("ANTES DA REGIAO", flush=True)

    with pascal_region(
        1,
        filename=Path(__file__).name,
        start_line=1,
        stop_line=1,
    ):
        deadline = time.perf_counter() + 2.0
        value = 1
        while time.perf_counter() < deadline:
            value = (value * 1664525 + 1013904223) & 0xFFFFFFFF

    print("DEPOIS DA REGIAO", flush=True)
    print("value =", value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
