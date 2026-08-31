#!/usr/bin/env python3

import json
import sys
from pathlib import Path


def _summarize(path: Path) -> dict:
    if not path.exists():
        return {
            "file": str(path),
            "exists": False,
            "run_count": 0,
            "runs_with_regions": 0,
            "runs_with_region_1": 0,
            "region_1_duration_s": None,
        }

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    data = payload.get("data", {}) or {}
    runs_with_regions = 0
    runs_with_region_1 = 0
    region_1_duration_s = None

    for run in data.values():
        if not isinstance(run, dict):
            continue
        regions = run.get("regions")
        if not isinstance(regions, dict):
            continue
        runs_with_regions += 1
        samples = regions.get("1")
        if not samples:
            continue
        runs_with_region_1 += 1
        first = samples[0]
        if (
            region_1_duration_s is None
            and isinstance(first, list)
            and len(first) >= 2
            and isinstance(first[0], (int, float))
            and isinstance(first[1], (int, float))
        ):
            region_1_duration_s = float(first[1]) - float(first[0])

    return {
        "file": str(path),
        "exists": True,
        "run_count": len(data),
        "runs_with_regions": runs_with_regions,
        "runs_with_region_1": runs_with_region_1,
        "region_1_duration_s": region_1_duration_s,
    }


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: summarize_pascal_loader_matrix.py baseline.json preload.json rtld_global.json",
            file=sys.stderr,
        )
        return 2

    names = ("baseline", "preload", "rtld_global")
    summary = {
        name: _summarize(Path(path))
        for name, path in zip(names, sys.argv[1:], strict=True)
    }

    print(json.dumps(summary, indent=2, sort_keys=True))

    successful = [
        name
        for name, result in summary.items()
        if result["runs_with_region_1"] > 0
    ]
    print("successful_modes=" + ",".join(successful))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
