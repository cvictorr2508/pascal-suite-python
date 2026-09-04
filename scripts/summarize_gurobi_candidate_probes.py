#!/usr/bin/env python3
"""Summarize JSON reports emitted by probe_gurobi_candidate.py."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


FIELDS = (
    "instance", "status", "classification", "gurobi_runtime_s",
    "optimize_wall_s", "read_wall_s", "node_count", "work",
    "peak_rss_mib", "variables", "constraints", "file_size_mib", "report",
)


def classify_report(
    document: dict[str, Any], target_min_s: float, target_max_s: float
) -> str:
    if document.get("error"):
        return "error"
    metrics = document.get("metrics", {})
    status_name = metrics.get("status_name")
    if status_name == "TIME_LIMIT":
        return "time_limit"
    if status_name != "OPTIMAL":
        return "non_optimal"
    runtime = metrics.get("gurobi_runtime_s")
    if not isinstance(runtime, (int, float)):
        return "invalid"
    if runtime < target_min_s:
        return "too_fast"
    if runtime <= target_max_s:
        return "target"
    return "slow"


def _instance_sort_key(value: str) -> tuple[int, str]:
    match = re.search(r"_instance_(\d+)$", value)
    return (int(match.group(1)), value) if match else (10**9, value)


def report_to_row(
    path: Path,
    document: dict[str, Any],
    target_min_s: float,
    target_max_s: float,
) -> dict[str, Any]:
    metrics = document.get("metrics", {})
    model = document.get("model", {})
    workload = Path(document.get("workload", path.stem))
    peak_rss_kib = document.get("peak_rss_kib")
    file_size_bytes = document.get("file_size_bytes")
    return {
        "instance": workload.stem,
        "status": metrics.get("status_name") or document.get("error", {}).get(
            "type", "UNKNOWN"
        ),
        "classification": classify_report(
            document, target_min_s, target_max_s
        ),
        "gurobi_runtime_s": metrics.get("gurobi_runtime_s"),
        "optimize_wall_s": metrics.get("optimize_wall_s"),
        "read_wall_s": metrics.get("read_wall_s"),
        "node_count": metrics.get("node_count"),
        "work": metrics.get("work"),
        "peak_rss_mib": (
            round(float(peak_rss_kib) / 1024.0, 3)
            if isinstance(peak_rss_kib, (int, float)) else None
        ),
        "variables": model.get("variables"),
        "constraints": model.get("constraints"),
        "file_size_mib": (
            round(float(file_size_bytes) / (1024.0 * 1024.0), 3)
            if isinstance(file_size_bytes, (int, float)) else None
        ),
        "report": str(path),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--csv-out", type=Path)
    parser.add_argument("--target-min", type=float, default=5.0)
    parser.add_argument("--target-max", type=float, default=30.0)
    parser.add_argument("--require-count", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.target_min < 0 or args.target_max < args.target_min:
        raise SystemExit("invalid target interval")

    paths = sorted(args.input_dir.glob("probe_*.json"))
    rows = []
    for path in paths:
        with path.open("r", encoding="utf-8") as stream:
            document = json.load(stream)
        rows.append(
            report_to_row(path, document, args.target_min, args.target_max)
        )
    rows.sort(key=lambda row: _instance_sort_key(str(row["instance"])))

    csv_out = args.csv_out or args.input_dir / "summary.csv"
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    with csv_out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print("\t".join(("instance", "status", "class", "runtime_s", "rss_mib")))
    for row in rows:
        print(
            "\t".join(
                str(value) for value in (
                    row["instance"], row["status"], row["classification"],
                    row["gurobi_runtime_s"], row["peak_rss_mib"],
                )
            )
        )
    print(f"summary={csv_out}")

    if args.require_count is not None and len(rows) != args.require_count:
        print(f"expected_reports={args.require_count} actual_reports={len(rows)}")
        return 2
    return 1 if any(row["classification"] == "error" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
