#!/usr/bin/env python3
"""Build a deterministic comparison from accepted Gurobi and SCIP matrices."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

EXPECTED_PROFILES = ("default", "presolve-off", "warm-start")
REGION_ID = "0.2"


class ComparisonError(ValueError):
    """Raised when campaign evidence cannot support a dual-solver comparison."""


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_record(path: Path) -> dict[str, Any]:
    return {
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _workload_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    names = set()
    for item in manifest.get("workloads", []):
        name = Path(str(item.get("path", ""))).name
        sha256 = item.get("sha256")
        size_bytes = item.get("size_bytes")
        if not name or not isinstance(sha256, str) or len(sha256) != 64:
            raise ComparisonError("Every workload must have a name and SHA-256")
        if not isinstance(size_bytes, int) or size_bytes <= 0:
            raise ComparisonError(f"Workload {name!r} has an invalid size")
        if name in names:
            raise ComparisonError(f"Duplicate workload name: {name}")
        names.add(name)
        records.append(
            {
                "name": name,
                "size_bytes": size_bytes,
                "sha256": sha256,
            }
        )
    if not records:
        raise ComparisonError("Campaign manifest contains no workloads")
    return sorted(records, key=lambda item: item["name"])


def _allocation_record(manifest: dict[str, Any]) -> dict[str, Any]:
    slurm = manifest.get("slurm")
    if not isinstance(slurm, dict):
        slurm = {}
    allocation = slurm.get("allocation")
    if not isinstance(allocation, dict):
        allocation = {}
    return {
        "partition": slurm.get("SLURM_JOB_PARTITION"),
        "requested_mode": allocation.get("requested_mode"),
        "scheduler_oversubscribe": allocation.get("scheduler_oversubscribe"),
        "scheduler_exclusive": allocation.get("scheduler_exclusive"),
        "explicit_policy_recorded": bool(allocation),
    }


def _load_campaign(root: Path) -> dict[str, Any]:
    root = root.resolve()
    summary_path = root / "profile_matrix_summary.json"
    manifest_path = root / "research_manifest.json"
    summary = _load_json(summary_path)
    manifest = _load_json(manifest_path)

    solver = summary.get("solver")
    if solver not in {"gurobi", "scip"}:
        raise ComparisonError(f"Unsupported solver in {summary_path}: {solver!r}")
    if manifest.get("experiment", {}).get("solver") != solver:
        raise ComparisonError(f"Solver mismatch in {root}")
    if summary.get("gate", {}).get("accepted") is not True:
        raise ComparisonError(f"{solver} profile matrix is not accepted")
    if manifest.get("source", {}).get("tracked_worktree_clean") is not True:
        raise ComparisonError(f"{solver} source worktree was not clean")

    profile_ids = tuple(sorted(summary.get("profiles", {})))
    if profile_ids != tuple(sorted(EXPECTED_PROFILES)):
        raise ComparisonError(
            f"{solver} profiles differ from {EXPECTED_PROFILES!r}: {profile_ids!r}"
        )
    for profile_id in EXPECTED_PROFILES:
        if summary["profiles"][profile_id].get("accepted") is not True:
            raise ComparisonError(f"{solver}/{profile_id} is not accepted")

    return {
        "root": root,
        "solver": solver,
        "summary": summary,
        "manifest": manifest,
        "summary_path": summary_path,
        "manifest_path": manifest_path,
        "workloads": _workload_records(manifest),
    }


def _positive_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ComparisonError(f"{label} must be numeric")
    number = float(value)
    if number <= 0:
        raise ComparisonError(f"{label} must be positive")
    return number


def _measurement_rows(campaign: dict[str, Any]) -> list[dict[str, Any]]:
    solver = campaign["solver"]
    grouped: dict[tuple[str, str, int], list[tuple[float, float, float]]] = (
        defaultdict(list)
    )
    for profile_id in EXPECTED_PROFILES:
        energy = campaign["summary"]["profiles"][profile_id]["energy"]
        for run in energy.get("runs", []):
            configuration = run.get("configuration", {})
            workload = Path(str(configuration.get("workload", ""))).name
            cores = configuration.get("cores")
            region = run.get("regions", {}).get(REGION_ID)
            if not workload or not isinstance(cores, int) or not isinstance(region, dict):
                raise ComparisonError(
                    f"{solver}/{profile_id} contains an incomplete run record"
                )
            duration = _positive_number(
                region.get("duration_s"),
                f"{solver}/{profile_id}/{workload} duration",
            )
            energy_j = _positive_number(
                region.get("energy_j"),
                f"{solver}/{profile_id}/{workload} energy",
            )
            grouped[(profile_id, workload, cores)].append(
                (duration, energy_j, duration * energy_j)
            )

    rows = []
    for (profile_id, workload, cores), values in sorted(grouped.items()):
        rows.append(
            {
                "solver": solver,
                "profile": profile_id,
                "workload": workload,
                "cores": cores,
                "valid_run_count": len(values),
                "median_solve_duration_s": statistics.median(
                    value[0] for value in values
                ),
                "median_solve_energy_j": statistics.median(
                    value[1] for value in values
                ),
                "median_solve_edp_js": statistics.median(
                    value[2] for value in values
                ),
            }
        )
    if not rows:
        raise ComparisonError(f"{solver} summary contains no valid measurements")
    return rows


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator


def build_comparison(
    gurobi_root: Path,
    scip_root: Path,
) -> dict[str, Any]:
    campaigns = [_load_campaign(gurobi_root), _load_campaign(scip_root)]
    by_solver = {campaign["solver"]: campaign for campaign in campaigns}
    if set(by_solver) != {"gurobi", "scip"}:
        raise ComparisonError("Inputs must contain one Gurobi and one SCIP campaign")

    gurobi_workloads = by_solver["gurobi"]["workloads"]
    scip_workloads = by_solver["scip"]["workloads"]
    if gurobi_workloads != scip_workloads:
        raise ComparisonError("Gurobi and SCIP workload fingerprints differ")

    measurements = []
    for solver in ("gurobi", "scip"):
        measurements.extend(_measurement_rows(by_solver[solver]))

    indexed = {
        (row["solver"], row["profile"], row["workload"], row["cores"]): row
        for row in measurements
    }
    paired = []
    for profile in EXPECTED_PROFILES:
        for workload in (item["name"] for item in gurobi_workloads):
            key = (profile, workload, 1)
            gurobi = indexed.get(("gurobi", *key))
            scip = indexed.get(("scip", *key))
            if gurobi is None or scip is None:
                raise ComparisonError(
                    f"Missing common one-core configuration: {profile}/{workload}"
                )
            paired.append(
                {
                    "profile": profile,
                    "workload": workload,
                    "cores": 1,
                    "gurobi_valid_run_count": gurobi["valid_run_count"],
                    "scip_valid_run_count": scip["valid_run_count"],
                    "scip_to_gurobi_duration_ratio": _ratio(
                        scip["median_solve_duration_s"],
                        gurobi["median_solve_duration_s"],
                    ),
                    "scip_to_gurobi_energy_ratio": _ratio(
                        scip["median_solve_energy_j"],
                        gurobi["median_solve_energy_j"],
                    ),
                    "scip_to_gurobi_edp_ratio": _ratio(
                        scip["median_solve_edp_js"],
                        gurobi["median_solve_edp_js"],
                    ),
                }
            )

    inputs = {}
    for solver in ("gurobi", "scip"):
        campaign = by_solver[solver]
        manifest = campaign["manifest"]
        inputs[solver] = {
            "profile_summary": _artifact_record(campaign["summary_path"]),
            "research_manifest": _artifact_record(campaign["manifest_path"]),
            "source": manifest.get("source"),
            "runtime": manifest.get("runtime"),
            "allocation": _allocation_record(manifest),
            "resources": manifest.get("experiment", {}).get("resources"),
            "repetitions": manifest.get("experiment", {}).get("repetitions"),
        }

    return {
        "schema_version": 1,
        "comparison_scope": {
            "region_id": REGION_ID,
            "region_semantics": "solve execution",
            "paired_resources": [1],
            "profiles": list(EXPECTED_PROFILES),
        },
        "inputs": inputs,
        "dataset": {
            "fingerprints_match": True,
            "workloads": gurobi_workloads,
        },
        "measurements": measurements,
        "paired_comparisons": paired,
        "gate": {
            "input_matrices_accepted": True,
            "source_worktrees_clean": True,
            "profile_contract_matches": True,
            "dataset_fingerprints_match": True,
            "common_one_core_configurations_complete": True,
            "accepted": True,
        },
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ComparisonError(f"Cannot write empty CSV: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_evidence(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "dual_solver_comparison.json"
    measurements_path = output_dir / "solver_measurements.csv"
    paired_path = output_dir / "paired_one_core_comparisons.csv"
    checksums_path = output_dir / "SHA256SUMS"

    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(measurements_path, report["measurements"])
    _write_csv(paired_path, report["paired_comparisons"])

    artifacts = (report_path, measurements_path, paired_path)
    checksums_path.write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in artifacts),
        encoding="utf-8",
    )
    return {
        "report": report_path,
        "measurements": measurements_path,
        "paired_comparisons": paired_path,
        "checksums": checksums_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic one-core Gurobi/SCIP comparisons from accepted "
            "profile-matrix evidence."
        )
    )
    parser.add_argument("--gurobi-root", type=Path, required=True)
    parser.add_argument("--scip-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()

    try:
        report = build_comparison(arguments.gurobi_root, arguments.scip_root)
        paths = write_evidence(report, arguments.output_dir)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ComparisonError) as exc:
        print(f"comparison_error={exc}", file=sys.stderr)
        return 2

    print(f"paired_configurations={len(report['paired_comparisons'])}")
    print(f"dataset_workloads={len(report['dataset']['workloads'])}")
    print(f"dual_solver_comparison_accepted={report['gate']['accepted']}")
    for name, path in paths.items():
        print(f"{name}={path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
