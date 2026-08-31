#!/usr/bin/env python3

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} RESULT.json", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    descriptor = payload.get("config", {}).get("data_descriptor", {})
    extras = descriptor.get("extras", {}) or {}
    data = payload.get("data", {}) or {}

    print(f"file={path}")
    print(f"values={descriptor.get('values', [])}")
    print("extras=")
    for name, desc in extras.items():
        print(f"  {name}: {desc.get('values', []) if isinstance(desc, dict) else desc}")

    if not data:
        print("data=<empty>")
        return 0

    first_key = next(iter(data))
    first_run = data[first_key]
    print(f"first_run={first_key}")
    print(f"first_run_keys={list(first_run.keys())}")
    print(f"regions={first_run.get('regions')}")

    for name in extras:
        if name == "regions":
            continue
        print(f"{name}={first_run.get(name)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
