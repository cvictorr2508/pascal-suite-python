#!/usr/bin/env python3
"""Read a preserved retry chain without writing files or importing solvers.

Exit 0: checked evidence and parameters agree; 2: evidence audit failed;
3: evidence checks passed but effective retry parameters differ.
Stored summaries support diagnostics only. Raw power is not reintegrated.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import statistics
from pathlib import Path


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return value


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def within(path: str | Path, root: Path) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Manifest reference escapes its declared evidence root")
    return resolved


def single(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"Expected one {pattern}, found {len(matches)}")
    return matches[0]


def contract(metadata: dict) -> dict:
    """Exclude local indexing, timing and outcomes, never effective parameters."""
    parameters = metadata["parameters"]
    required = (
        "seed_requested",
        "seed_effective",
        "threads_requested",
        "threads_effective",
        "parallelism_mode",
        "profile_requested",
        "profile_effective",
    )
    for key in required:
        if key not in parameters or parameters[key] is None:
            raise ValueError(f"Missing required parameter: {key}")
    for key in ("seed_requested", "seed_effective"):
        if type(parameters[key]) is not int or parameters[key] < 0:
            raise ValueError(f"Invalid seed: {key}")
    return {
        "solver": metadata["solver"],
        "workload": metadata["workload"],
        "profile": metadata["profile"],
        "cores": metadata["cores"],
        "objective_sense": metadata["objective_sense"]["effective_name"],
        "parameters": parameters,
    }


def differences(left: dict, right: dict, prefix: str = "") -> list[str]:
    result = []
    for key in sorted(left.keys() | right.keys()):
        name = f"{prefix}.{key}" if prefix else key
        if key not in left or key not in right:
            result.append(name)
        elif isinstance(left[key], dict) and isinstance(right[key], dict):
            result.extend(differences(left[key], right[key], name))
        elif left[key] != right[key]:
            result.append(name)
    return result


def cell_statistics(summary: dict, input_index: int, region_id: str = "0.2") -> dict:
    rows = [
        row
        for row in summary["profiles"]["default"]["energy"]["runs"]
        if row["configuration"]["input_index"] == input_index
        and row["configuration"]["cores"] == 1
    ]
    if not rows:
        raise ValueError("No valid stored summary rows for the affected cell")
    duration, energy, edp = [], [], []
    for row in rows:
        region = row["regions"][region_id]
        seconds, joules = region["duration_s"], region["energy_j"]
        for value in (seconds, joules):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"Invalid stored region-{region_id} measurement")
        duration.append(seconds)
        energy.append(joules)
        edp.append(seconds * joules)
    return {
        "telemetry_valid_count": len(rows),
        "median_duration_s": statistics.median(duration),
        "median_energy_j": statistics.median(energy),
        "median_edp_js": statistics.median(edp),
    }


def audit(manifest_path: Path) -> dict:
    manifest = load(manifest_path)
    if (
        manifest["kind"] != "telemetry-retry-replacement"
        or manifest["schema_version"] != 1
    ):
        raise ValueError("Unsupported composition kind")
    roots = {
        "original": Path(manifest["original_root"]).resolve(),
        "retry": Path(manifest["retry_root"]).resolve(),
        "composite": Path(manifest["output_root"]).resolve(),
    }
    if len(set(roots.values())) != 3:
        raise ValueError("Original, retry and composite roots must be distinct")
    checks = {}

    def check(name: str, condition: bool) -> None:
        checks[name] = bool(condition)

    def check_hash(name: str, path: Path, expected: str) -> None:
        check(name, digest(path) == expected)

    documents, summaries = {}, {}
    for label in ("original", "retry"):
        root = roots[label]
        path = single(root / "scip/default", "*_batch_pascal.json")
        documents[label] = load(path)
        summaries[label] = load(root / "profile_matrix_summary.json")
        for suffix, source_path in (
            ("pascal_json", path),
            ("profile_summary", root / "profile_matrix_summary.json"),
            ("research_manifest", root / "research_manifest.json"),
        ):
            name = f"{label}_{suffix}"
            check_hash(name, source_path, manifest["source_hashes"][name])
        source = load(root / "research_manifest.json")["source"]
        check(f"{label}_commit", source["git_commit"] == manifest["source_commit"])

    root = roots["composite"]
    derived = manifest["derived_files"]
    composite_path = within(derived["composite_pascal_json"], root)
    documents["composite"] = load(composite_path)
    summaries["composite"] = load(root / "profile_matrix_summary.json")
    for name, hash_name in (
        ("composite_pascal_json", "composite_pascal_sha256"),
        ("viewer_json", "viewer_json_sha256"),
        ("research_manifest", "research_manifest_sha256"),
    ):
        check_hash(name, within(derived[name], root), derived[hash_name])
    check(
        "viewer_matches_composite",
        load(within(derived["viewer_json"], root)) == documents["composite"],
    )

    expected = copy.deepcopy(documents["original"])
    check(
        "fixed_replacement_map",
        [(row["original_run"], row["retry_run"]) for row in manifest["replacements"]]
        == [("1;2;2", "1;0;1"), ("1;2;3", "1;0;2")],
    )
    original_invalid = {
        row["run"]
        for row in summaries["original"]["profiles"]["default"]["energy"][
            "invalid_runs"
        ]
    }
    retry_valid = {
        row["run"]
        for row in summaries["retry"]["profiles"]["default"]["energy"]["runs"]
    }
    original_valid = {
        row["run"]
        for row in summaries["original"]["profiles"]["default"]["energy"]["runs"]
    }
    composite_valid_rows = summaries["composite"]["profiles"]["default"]["energy"][
        "runs"
    ]
    composite_valid = {row["run"] for row in composite_valid_rows}
    check(
        "composite_valid_run_membership",
        composite_valid == original_valid | {"1;2;2", "1;2;3"}
        and len(composite_valid) == len(composite_valid_rows),
    )
    for replacement in manifest["replacements"]:
        old, new = replacement["original_run"], replacement["retry_run"]
        check(f"invalid_original:{old}", old in original_invalid)
        check(f"valid_retry:{new}", new in retry_valid)
        expected["data"][old] = copy.deepcopy(documents["retry"]["data"][new])
    check("complete_analyzer_copy", expected == documents["composite"])

    originals = sorted((roots["original"] / "scip/default").glob("meta_c1_i2_*.json"))
    if len(originals) != 6 or len(manifest["metadata_added"]) != 2:
        raise ValueError("Expected six original metadata records and two retries")
    reference = contract(load(originals[0]))
    configuration = manifest["configuration"]
    check(
        "declared_configuration",
        all(
            reference[key] == configuration[key]
            for key in ("solver", "cores", "workload")
        )
        and reference["profile"]["id"] == configuration["profile"]
        and configuration["original_input_index"] == 2
        and configuration["retry_input_index"] == 0,
    )
    check(
        "original_contract_uniform",
        all(contract(load(path)) == reference for path in originals),
    )
    removed = set()
    for entry in manifest["metadata_removed"]:
        path = within(entry["path"], roots["original"])
        check_hash(f"removed:{path.name}", path, entry["sha256"])
        removed.add(path.name)
    check("two_unique_removed", len(removed) == len(manifest["metadata_removed"]) == 2)
    check(
        "removed_chronological_positions", removed == {p.name for p in originals[1:3]}
    )

    mismatch, retry_times, added_names = [], [], set()
    for entry in manifest["metadata_added"]:
        source = within(entry["retry_source"], roots["retry"])
        destination = within(entry["composite_destination"], root)
        check_hash(f"retry:{source.name}", source, entry["retry_source_sha256"])
        check_hash(f"added:{destination.name}", destination, entry["composite_sha256"])
        metadata = load(source)
        mismatch.append(
            {
                "file": source.name,
                "fields": differences(reference, contract(metadata)),
                "original_seed": reference["parameters"]["seed_effective"],
                "retry_seed": metadata["parameters"]["seed_effective"],
            }
        )
        retry_times.append(metadata["start_timestamp"])
        remap = entry["remapped_input_index"]
        check(f"declared_remap:{source.name}", remap == {"from": 0, "to": 2})
        check(f"source_index:{source.name}", metadata["input_idx"] == remap["from"])
        metadata["input_idx"] = remap["to"]
        check(f"index_only_remap:{destination.name}", metadata == load(destination))
        added_names.add(destination.name)
    check("retry_chronological_order", retry_times == sorted(set(retry_times)))
    check("two_unique_added", len(added_names) == 2)

    original_files = list((roots["original"] / "scip/default").glob("meta_*.json"))
    for path in original_files:
        if path.name not in removed:
            check_hash(
                f"retained:{path.name}", root / "scip/default" / path.name, digest(path)
            )
    expected_names = {p.name for p in original_files} - removed | added_names
    observed_names = {p.name for p in (root / "scip/default").glob("meta_*.json")}
    check("complete_metadata_set", observed_names == expected_names)
    for profile in ("presolve-off", "warm-start"):
        source_dir = roots["original"] / "scip" / profile
        target_dir = root / "scip" / profile
        # These profiles are outside the replacement scope. Their derived
        # summaries were regenerated, so compare preserved files only.
        source_files = {
            p.relative_to(source_dir)
            for p in source_dir.rglob("*")
            if p.is_file() and p.name != "summary.json"
        }
        target_files = {
            p.relative_to(target_dir)
            for p in target_dir.rglob("*")
            if p.is_file() and p.name != "summary.json"
        }
        check(f"unchanged_profile_files:{profile}", source_files == target_files)
        for relative in source_files:
            check_hash(
                f"unchanged:{profile}/{relative}",
                target_dir / relative,
                digest(source_dir / relative),
            )

    stats = {
        name: cell_statistics(summaries[name], index)
        for name, index in (("original", 2), ("retry", 0), ("composite", 2))
    }
    equivalent = all(not item["fields"] for item in mismatch)
    check(
        "affected_cell_valid_counts",
        [
            stats[name]["telemetry_valid_count"]
            for name in ("original", "retry", "composite")
        ]
        == [4, 2, 6],
    )
    baseline = stats["original"]
    change = {
        key: 100 * (stats["composite"][key] / baseline[key] - 1)
        for key in ("median_duration_s", "median_energy_j", "median_edp_js")
    }
    pipeline_stats = {
        name: cell_statistics(summaries[name], index, "0")
        for name, index in (("original", 2), ("retry", 0), ("composite", 2))
    }
    pipeline_change = {
        key: 100
        * (pipeline_stats["composite"][key] / pipeline_stats["original"][key] - 1)
        for key in ("median_duration_s", "median_energy_j", "median_edp_js")
    }
    return {
        "integrity_accepted": all(checks.values()),
        "failed_checks": [key for key, value in checks.items() if not value],
        "checks_performed": len(checks),
        "retry_parameter_equivalence": equivalent,
        "parameter_differences": mismatch,
        "cell_diagnostics": stats,
        "cell_diagnostics_region": "0.2",
        "composite_vs_original_median_change_percent": change,
        "pipeline_region_0_diagnostics": pipeline_stats,
        "pipeline_composite_vs_original_median_change_percent": pipeline_change,
        "composite_summary_sha256_observed": digest(
            root / "profile_matrix_summary.json"
        ),
        "same_contract_valid_count": (
            stats["composite"]["telemetry_valid_count"]
            if equivalent
            else stats["original"]["telemetry_valid_count"]
        ),
        "diagnostic_only": True,
        "raw_power_reintegrated": False,
        "stored_summary_values_independently_recomputed": False,
        "scheduler_allocation_equivalence_checked": False,
        "causal_seed_effect_estimated": False,
        "publication_artifacts_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = audit(args.manifest)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print(json.dumps({"integrity_accepted": False, "error": str(error)}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["integrity_accepted"]:
        return 2
    return 0 if report["retry_parameter_equivalence"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
