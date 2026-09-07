#!/usr/bin/env python3
"""Consolidate energy gates and runner metadata for a solver-profile matrix."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ENERGY_SCRIPT = Path(__file__).with_name("summarize_refactor28_nested_energy.py")
SPEC = importlib.util.spec_from_file_location("nested_energy_summary", ENERGY_SCRIPT)
ENERGY_SUMMARY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ENERGY_SUMMARY)


class ProfileMatrixError(ValueError):
    """Raised when profile artifacts do not satisfy the matrix contract."""


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _single_file(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise ProfileMatrixError(
            f"Expected one {pattern!r} in {directory}, found {len(matches)}"
        )
    return matches[0]


def _metadata_errors(
    profile_id: str,
    profile_kind: str,
    metadata_paths: list[Path],
) -> list[str]:
    errors = []
    for path in metadata_paths:
        metadata = _load_json(path)
        if metadata.get("error"):
            errors.append(f"{path.name}: runner error: {metadata['error']}")
        if metadata.get("profile", {}).get("id") != profile_id:
            errors.append(f"{path.name}: profile ID mismatch")
        if profile_kind == "presolve-off":
            effective = metadata.get("parameters", {}).get("profile_effective", {})
            if effective.get("Presolve") != 0:
                errors.append(f"{path.name}: effective Presolve is not zero")
        if profile_kind == "warm-start":
            initial_solution = metadata.get("initial_solution", {})
            if initial_solution.get("applied") is not True:
                errors.append(f"{path.name}: initial solution was not applied")
            if initial_solution.get("format") not in {"mst", "sol", "json"}:
                errors.append(f"{path.name}: unsupported initial-solution format")
    return errors


def summarize_profile_matrix(
    output_root: Path,
    *,
    required_runs: int = 5,
    required_configurations: int = 15,
    max_median_error_percent: float = 5.0,
    preferred_max_cv_percent: float = 10.0,
) -> dict[str, Any]:
    output_root = output_root.resolve()
    manifest_path = output_root / "research_manifest.json"
    manifest = _load_json(manifest_path)
    experiment = manifest.get("experiment", {})
    solver = experiment.get("solver")
    profiles = experiment.get("profiles")
    workloads = [item["path"] for item in manifest.get("workloads", [])]
    if solver != "gurobi":
        raise ProfileMatrixError(f"Unsupported solver for this sprint: {solver!r}")
    if not isinstance(profiles, list) or not profiles:
        raise ProfileMatrixError("Research manifest contains no profiles")

    expected_attempts = (
        len(workloads)
        * len(experiment.get("resources", []))
        * int(experiment.get("repetitions", 0))
    )
    if expected_attempts < 1:
        raise ProfileMatrixError("Research manifest has an empty experiment matrix")

    profile_results = {}
    for profile in profiles:
        profile_id = profile["id"]
        profile_kind = profile["kind"]
        profile_dir = output_root / solver / profile_id
        telemetry_path = _single_file(profile_dir, "*_pascal.json")
        base_config_path = profile_dir / "base_config.json"
        base_config = _load_json(base_config_path)
        if base_config.get("profile", {}).get("id") != profile_id:
            raise ProfileMatrixError(f"Base-config profile mismatch for {profile_id}")

        metadata_paths = sorted(profile_dir.glob("meta_*.json"))
        metadata_errors = _metadata_errors(
            profile_id,
            profile_kind,
            metadata_paths,
        )
        if len(metadata_paths) != expected_attempts:
            metadata_errors.append(
                "Expected "
                f"{expected_attempts} metadata files, found {len(metadata_paths)}"
            )

        summary = ENERGY_SUMMARY.summarize_document(
            _load_json(telemetry_path),
            required_runs=required_runs,
            max_median_error_percent=max_median_error_percent,
            preferred_max_cv_percent=preferred_max_cv_percent,
            workloads=workloads,
            required_configurations=required_configurations,
        )
        profile_result = {
            "profile_id": profile_id,
            "profile_kind": profile_kind,
            "telemetry_path": str(telemetry_path),
            "metadata_count": len(metadata_paths),
            "expected_attempt_count": expected_attempts,
            "metadata_errors": metadata_errors,
            "energy": summary,
            "accepted": (
                not metadata_errors
                and summary["configuration_count_accepted"]
                and summary["accuracy"]["accepted"]
            ),
        }
        profile_results[profile_id] = profile_result
        (profile_dir / "summary.json").write_text(
            json.dumps(profile_result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    expected_profile_ids = {"default", "presolve-off", "warm-start"}
    observed_profile_ids = set(profile_results)
    profile_set_accepted = observed_profile_ids == expected_profile_ids
    accuracy_accepted = all(
        result["accepted"] for result in profile_results.values()
    )
    variability_preferred = all(
        result["energy"]["variability"]["preferred"]
        for result in profile_results.values()
    )
    return {
        "schema_version": 1,
        "research_manifest": str(manifest_path),
        "source": manifest.get("source"),
        "solver": solver,
        "profile_ids": sorted(observed_profile_ids),
        "required_profile_ids": sorted(expected_profile_ids),
        "profile_set_accepted": profile_set_accepted,
        "expected_attempt_count_per_profile": expected_attempts,
        "profiles": profile_results,
        "gate": {
            "accuracy_accepted": accuracy_accepted,
            "variability_preferred": variability_preferred,
            "accepted": profile_set_accepted and accuracy_accepted,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a complete Gurobi profile experiment matrix."
    )
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--require-runs", type=int, default=5)
    parser.add_argument("--require-configurations", type=int, default=15)
    parser.add_argument("--max-median-error-percent", type=float, default=5.0)
    parser.add_argument("--preferred-max-cv-percent", type=float, default=10.0)
    parser.add_argument("--output-json", type=Path)
    arguments = parser.parse_args()

    try:
        summary = summarize_profile_matrix(
            arguments.output_root,
            required_runs=arguments.require_runs,
            required_configurations=arguments.require_configurations,
            max_median_error_percent=arguments.max_median_error_percent,
            preferred_max_cv_percent=arguments.preferred_max_cv_percent,
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ProfileMatrixError,
        ENERGY_SUMMARY.EnergySummaryError,
    ) as exc:
        print(f"validation_error={exc}", file=sys.stderr)
        return 2

    output_path = arguments.output_json or (
        arguments.output_root / "profile_matrix_summary.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for profile_id, result in summary["profiles"].items():
        energy = result["energy"]
        print(
            f"profile={profile_id} attempted={energy['attempted_run_count']} "
            f"valid={energy['run_count']} invalid={energy['invalid_run_count']} "
            f"configurations={energy['configuration_count']} "
            f"median_error_percent="
            f"{energy['accuracy']['median_absolute_error_percent']:.6f} "
            f"max_cv_percent="
            f"{energy['variability']['maximum_group_region_0_cv_percent']:.6f} "
            f"accepted={result['accepted']}"
        )
    print(f"variability_preferred={summary['gate']['variability_preferred']}")
    print(f"profile_matrix_accepted={summary['gate']['accepted']}")
    print(f"summary={output_path.resolve()}")
    return 0 if summary["gate"]["accepted"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
