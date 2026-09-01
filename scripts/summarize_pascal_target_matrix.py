#!/usr/bin/env python3

import json
import sys
from pathlib import Path


def summarize(path: Path, region_id: str) -> dict:
    if not path.exists():
        return {
            "file": str(path),
            "exists": False,
            "run_count": 0,
            "runs_with_regions": 0,
            "runs_with_region": 0,
            "region_duration_s": None,
        }

    payload = json.loads(path.read_text(encoding="utf-8"))
    data = payload.get("data") or {}
    runs_with_regions = 0
    runs_with_region = 0
    duration = None

    for run in data.values():
        if not isinstance(run, dict):
            continue
        regions = run.get("regions")
        if not isinstance(regions, dict):
            continue
        runs_with_regions += 1
        samples = regions.get(region_id)
        if not samples:
            continue
        runs_with_region += 1
        first = samples[0]
        if (
            duration is None
            and isinstance(first, list)
            and len(first) >= 2
            and isinstance(first[0], (int, float))
            and isinstance(first[1], (int, float))
        ):
            duration = float(first[1]) - float(first[0])

    return {
        "file": str(path),
        "exists": True,
        "run_count": len(data),
        "runs_with_regions": runs_with_regions,
        "runs_with_region": runs_with_region,
        "region_duration_s": duration,
    }


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: summarize_pascal_target_matrix.py selftest.json exec.json spawn.json",
            file=sys.stderr,
        )
        return 2

    cases = {
        "linked_selftest": (Path(sys.argv[1]), "9"),
        "linked_exec": (Path(sys.argv[2]), "1"),
        "linked_spawn": (Path(sys.argv[3]), "1"),
    }
    summary = {
        name: summarize(path, region_id)
        for name, (path, region_id) in cases.items()
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    successful = [
        name for name, result in summary.items() if result["runs_with_region"] > 0
    ]
    print("successful_target_modes=" + ",".join(successful))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
