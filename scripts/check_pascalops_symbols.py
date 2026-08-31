#!/usr/bin/env python3
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.instrumentation.pascalops import instrumentation_status  # noqa: E402


def main() -> int:
    status = instrumentation_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0 if status["available"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
