#!/usr/bin/env python3
"""Export a deterministic, path-neutral dual-solver evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

SOLVERS = ("gurobi", "scip")
COMPARISON_FILES = (
    "dual_solver_comparison.json",
    "solver_measurements.csv",
    "paired_one_core_comparisons.csv",
)
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


class EvidenceError(ValueError):
    """Raised when source evidence cannot produce a portable manifest."""


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        document = json.load(stream)
    if not isinstance(document, dict):
        raise EvidenceError(f"Expected a JSON object: {path.name}")
    return document


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact(path: Path, logical_path: str) -> dict[str, Any]:
    return {
        "logical_path": logical_path,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _verify_artifact(path: Path, expected: dict[str, Any], label: str) -> None:
    observed = _artifact(path, label)
    if expected.get("name") != path.name:
        raise EvidenceError(f"{label} filename does not match the comparison report")
    for field in ("size_bytes", "sha256"):
        if expected.get(field) != observed[field]:
            raise EvidenceError(f"{label} {field} does not match the comparison report")


def _portable_configuration(manifest: dict[str, Any]) -> dict[str, Any]:
    configuration = manifest.get("configuration")
    if not isinstance(configuration, dict):
        raise EvidenceError("Campaign manifest has no configuration record")
    path = Path(str(configuration.get("path", "")))
    return {
        "name": path.name,
        "size_bytes": configuration.get("size_bytes"),
        "sha256": configuration.get("sha256"),
    }


def _portable_initial_solutions(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for item in manifest.get("initial_solutions", []):
        records.append(
            {
                "name": Path(str(item.get("path", ""))).name,
                "profile_id": item.get("profile_id"),
                "workload": Path(str(item.get("workload", ""))).name,
                "size_bytes": item.get("size_bytes"),
                "sha256": item.get("sha256"),
            }
        )
    return sorted(records, key=lambda item: (str(item["profile_id"]), item["name"]))


def _profile_record(profile_id: str, result: dict[str, Any]) -> dict[str, Any]:
    energy = result.get("energy", {})
    accuracy = energy.get("accuracy", {})
    variability = energy.get("variability", {})
    return {
        "id": profile_id,
        "kind": result.get("profile_kind"),
        "accepted": result.get("accepted"),
        "attempted_runs": energy.get("attempted_run_count"),
        "valid_runs": energy.get("run_count"),
        "invalid_runs": energy.get("invalid_run_count"),
        "configurations": energy.get("configuration_count"),
        "median_absolute_energy_error_percent": accuracy.get(
            "median_absolute_error_percent"
        ),
        "accuracy_accepted": accuracy.get("accepted"),
        "maximum_region_0_cv_percent": variability.get(
            "maximum_group_region_0_cv_percent"
        ),
        "variability_preferred": variability.get("preferred"),
    }


def _campaign_record(
    solver: str,
    root: Path,
    comparison_input: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = root / "research_manifest.json"
    summary_path = root / "profile_matrix_summary.json"
    manifest = _load_json(manifest_path)
    summary = _load_json(summary_path)

    _verify_artifact(
        manifest_path,
        comparison_input.get("research_manifest", {}),
        f"{solver}/research_manifest.json",
    )
    _verify_artifact(
        summary_path,
        comparison_input.get("profile_summary", {}),
        f"{solver}/profile_matrix_summary.json",
    )
    if summary.get("solver") != solver:
        raise EvidenceError(f"Unexpected solver in {solver} summary")
    if summary.get("gate", {}).get("accepted") is not True:
        raise EvidenceError(f"{solver} profile matrix is not accepted")

    source = manifest.get("source", {})
    if source.get("tracked_worktree_clean") is not True:
        raise EvidenceError(f"{solver} source worktree was not clean")
    runtime = manifest.get("runtime", {})
    experiment = manifest.get("experiment", {})
    slurm = manifest.get("slurm", {})
    allocation = slurm.get("allocation", {})

    record = {
        "solver": solver,
        "source": {
            "git_commit": source.get("git_commit"),
            "git_branch": source.get("git_branch"),
            "tracked_worktree_clean": source.get("tracked_worktree_clean"),
        },
        "runtime": {
            "platform": runtime.get("platform"),
            "python_version": runtime.get("python_version"),
            "packages": runtime.get("packages", {}),
        },
        "configuration": _portable_configuration(manifest),
        "experiment": {
            "resources": experiment.get("resources"),
            "repetitions": experiment.get("repetitions"),
            "profiles": [
                _profile_record(profile_id, result)
                for profile_id, result in sorted(summary.get("profiles", {}).items())
            ],
        },
        "initial_solutions": _portable_initial_solutions(manifest),
        "slurm": {
            "job_id": slurm.get("SLURM_JOB_ID"),
            "job_name": slurm.get("SLURM_JOB_NAME"),
            "partition": slurm.get("SLURM_JOB_PARTITION"),
            "cpus_per_task": slurm.get("SLURM_CPUS_PER_TASK"),
            "allocation": {
                "requested_mode": allocation.get("requested_mode"),
                "scheduler_oversubscribe": allocation.get(
                    "scheduler_oversubscribe"
                ),
                "scheduler_exclusive": allocation.get("scheduler_exclusive"),
            },
        },
    }
    artifacts = [
        _artifact(manifest_path, f"{solver}/research_manifest.json"),
        _artifact(summary_path, f"{solver}/profile_matrix_summary.json"),
    ]
    return record, artifacts


def _verify_comparison_checksums(root: Path) -> list[dict[str, Any]]:
    checksum_path = root / "SHA256SUMS"
    entries: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64 or Path(name).name != name:
            raise EvidenceError("Comparison SHA256SUMS contains an invalid entry")
        entries[name] = digest
    if set(entries) != set(COMPARISON_FILES):
        raise EvidenceError("Comparison SHA256SUMS does not list the expected files")

    artifacts = []
    for name in COMPARISON_FILES:
        path = root / name
        if _sha256(path) != entries[name]:
            raise EvidenceError(f"Checksum mismatch for comparison artifact {name}")
        artifacts.append(_artifact(path, f"comparison/{name}"))
    return artifacts


def _median_ratios(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("paired_comparisons", [])
    profiles = report.get("comparison_scope", {}).get("profiles", [])
    result = []
    for profile_id in profiles:
        selected = [row for row in rows if row.get("profile") == profile_id]
        if not selected:
            raise EvidenceError(f"No paired comparisons for profile {profile_id}")
        result.append(
            {
                "profile": profile_id,
                "paired_configurations": len(selected),
                "median_scip_to_gurobi_duration_ratio": statistics.median(
                    row["scip_to_gurobi_duration_ratio"] for row in selected
                ),
                "median_scip_to_gurobi_energy_ratio": statistics.median(
                    row["scip_to_gurobi_energy_ratio"] for row in selected
                ),
                "median_scip_to_gurobi_edp_ratio": statistics.median(
                    row["scip_to_gurobi_edp_ratio"] for row in selected
                ),
            }
        )
    return result


def _reject_absolute_paths(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_absolute_paths(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_absolute_paths(child, f"{location}[{index}]")
    elif isinstance(value, str) and (
        value.startswith("/") or WINDOWS_ABSOLUTE.match(value)
    ):
        raise EvidenceError(f"Absolute path leaked into {location}")


def build_portable_manifest(
    gurobi_root: Path,
    scip_root: Path,
    comparison_root: Path,
) -> dict[str, Any]:
    comparison_root = comparison_root.resolve()
    report = _load_json(comparison_root / "dual_solver_comparison.json")
    gate = report.get("gate", {})
    claim_status = report.get("comparison_scope", {}).get(
        "performance_claim_status"
    )
    if gate.get("accepted") is not True or claim_status != "controlled-comparison":
        raise EvidenceError("Dual-solver comparison is not controlled and accepted")

    campaigns = []
    artifacts = []
    roots = {"gurobi": gurobi_root.resolve(), "scip": scip_root.resolve()}
    for solver in SOLVERS:
        record, campaign_artifacts = _campaign_record(
            solver,
            roots[solver],
            report.get("inputs", {}).get(solver, {}),
        )
        campaigns.append(record)
        artifacts.extend(campaign_artifacts)
    artifacts.extend(_verify_comparison_checksums(comparison_root))

    manifest = {
        "schema_version": 1,
        "evidence_class": "controlled-dual-solver-research-mvp",
        "scope": report.get("comparison_scope"),
        "gate": gate,
        "dataset": report.get("dataset"),
        "campaigns": campaigns,
        "profile_median_ratios": _median_ratios(report),
        "artifacts": sorted(artifacts, key=lambda item: item["logical_path"]),
    }
    _reject_absolute_paths(manifest)
    return manifest


def write_portable_evidence(manifest: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise EvidenceError(f"Output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "evidence_manifest.json"
    checksums_path = output_dir / "SHA256SUMS"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksums_path.write_text(
        f"{_sha256(manifest_path)}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    return {"manifest": manifest_path, "checksums": checksums_path}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a deterministic, path-neutral research evidence manifest."
    )
    parser.add_argument("--gurobi-root", type=Path, required=True)
    parser.add_argument("--scip-root", type=Path, required=True)
    parser.add_argument("--comparison-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        manifest = build_portable_manifest(
            arguments.gurobi_root,
            arguments.scip_root,
            arguments.comparison_root,
        )
        paths = write_portable_evidence(manifest, arguments.output_dir)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, EvidenceError) as exc:
        print(f"evidence_error={exc}", file=sys.stderr)
        return 2
    print(f"evidence_class={manifest['evidence_class']}")
    print(f"campaigns={len(manifest['campaigns'])}")
    print(f"paired_configurations={len(manifest['dataset']['workloads']) * 3}")
    for name, path in paths.items():
        print(f"{name}={path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

