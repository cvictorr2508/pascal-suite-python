#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.validation.pascal_energy import validate_pascal_energy_file  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Classify a native PaScal JSON file as directly usable by the Viewer or "
            "derivable from region intervals and sampled RAPL power."
        )
    )
    parser.add_argument("json_path", help="Path to the JSON file produced by pascalanalyzer")
    parser.add_argument(
        "--region-id",
        type=int,
        default=1,
        help="Region of interest (default: 1 = model.optimize())",
    )
    parser.add_argument(
        "--accept-sampled",
        action="store_true",
        help=(
            "Accept regional telemetry with sampled RAPL power even when the "
            "Viewer still has to perform the integration."
        ),
    )
    parser.add_argument(
        "--require-nonzero-energy",
        action="store_true",
        help=(
            "Fail when the region exists but all energy observations are zero. "
            "Do not use this option with the dummy workload."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = validate_pascal_energy_file(
        args.json_path,
        required_region_id=args.region_id,
    )
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))

    accepted = report.viewer_energy_ready or (
        args.accept_sampled and report.sampled_energy_derivable
    )
    if not accepted:
        return 2
    if args.require_nonzero_energy and not report.required_region_has_nonzero_energy:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
