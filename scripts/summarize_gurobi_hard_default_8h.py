#!/usr/bin/env python3
"""Validate all shards and build a compact PaScal Viewer energy artifact."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ENERGY_SCRIPT = SCRIPT_DIR / "summarize_refactor28_nested_energy.py"
ENERGY_SPEC = importlib.util.spec_from_file_location(
    "nested_energy_summary", ENERGY_SCRIPT
)
ENERGY = importlib.util.module_from_spec(ENERGY_SPEC)
assert ENERGY_SPEC.loader is not None
ENERGY_SPEC.loader.exec_module(ENERGY)

sys.path.insert(0, str(SCRIPT_DIR))
from run_gurobi_hard_default_8h_shard import (  # noqa: E402
    campaign_shards,
    load_configuration,
)


class CampaignSummaryError(ValueError):
    """Raised when a shard violates the campaign evidence contract."""


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _single(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise CampaignSummaryError(
            f"expected one {pattern!r} under {directory}, found {len(matches)}"
        )
    return matches[0]


def _compact_config(first_config: dict[str, Any], workloads: list[str]) -> dict:
    config = copy.deepcopy(first_config)
    descriptor = config["data_descriptor"]
    descriptor["values"] = [
        value for value in descriptor.get("values", []) if value != "rapl-sysfs"
    ]
    extras = descriptor.setdefault("extras", {})
    extras.pop("sensors", None)
    extras["rapl-sysfs"] = {"values": ["region_energy"]}
    descriptor["keys"] = ["cores", "input", "repetitions"]
    config["command"] = (
        "derived-viewer-artifact -c 1,2,4 -i "
        + ",".join(workloads)
        + " -r 6 --rple sysfs --rpls sysfs"
    )
    config["derived_artifact"] = {
        "kind": "validated-regional-energy",
        "source": "configuration-sharded PaScal Analyzer outputs",
        "raw_power_samples_retained": False,
    }
    return config


def summarize_campaign(
    *, config_path: Path, campaign_root: Path, required_runs: int = 5
) -> dict[str, Any]:
    """Validate a complete campaign and emit compact Viewer-compatible data."""

    configuration = load_configuration(config_path)
    shards = campaign_shards(configuration)
    workloads = [str(shard.workload) for shard in shards[:5]]
    compact_data: dict[str, Any] = {}
    shard_records = []
    all_valid_runs = []
    all_invalid_runs = []
    configuration_records = []
    first_config = None
    source_commits = set()

    for shard in shards:
        shard_root = campaign_root / "shards" / shard.identifier
        profile_root = shard_root / "gurobi" / "default"
        manifest_path = shard_root / "research_manifest.json"
        telemetry_path = _single(profile_root, "*_pascal.json")
        manifest = _load_json(manifest_path)
        telemetry = _load_json(telemetry_path)
        if first_config is None:
            first_config = telemetry["config"]

        source = manifest.get("source", {})
        source_commit = source.get("git_commit")
        if not source_commit or source.get("tracked_worktree_clean") is not True:
            raise CampaignSummaryError(
                f"shard {shard.identifier} lacks clean source provenance"
            )
        source_commits.add(source_commit)
        experiment = manifest.get("experiment", {})
        if experiment.get("resources") != [shard.cores]:
            raise CampaignSummaryError(f"resource mismatch in {shard.identifier}")
        profiles = experiment.get("profiles") or []
        if len(profiles) != 1:
            raise CampaignSummaryError(f"profile mismatch in {shard.identifier}")
        parameters = profiles[0].get("parameters") or {}
        if parameters != {"TimeLimit": 28800}:
            raise CampaignSummaryError(
                f"TimeLimit mismatch in {shard.identifier}: {parameters}"
            )
        allocation = manifest.get("slurm", {}).get("allocation", {})
        if allocation.get("requested_mode") != "exclusive":
            raise CampaignSummaryError(
                f"exclusive allocation not recorded in {shard.identifier}"
            )
        if allocation.get("scheduler_oversubscribe") != "NO":
            raise CampaignSummaryError(
                f"scheduler did not confirm OverSubscribe=NO in "
                f"{shard.identifier}: {allocation}"
            )

        metadata_paths = sorted(profile_root.glob("meta_*.json"))
        if len(metadata_paths) != 6:
            raise CampaignSummaryError(
                f"expected six metadata files in {shard.identifier}, "
                f"found {len(metadata_paths)}"
            )
        metadata = [_load_json(path) for path in metadata_paths]
        for record in metadata:
            if record.get("error"):
                raise CampaignSummaryError(
                    f"runner error in {shard.identifier}: {record['error']}"
                )
            if record.get("cores") != shard.cores:
                raise CampaignSummaryError(
                    f"metadata core mismatch in {shard.identifier}"
                )
            if record.get("input_idx") != shard.input_index:
                raise CampaignSummaryError(
                    f"metadata input mismatch in {shard.identifier}"
                )
            parameters_record = record.get("parameters", {})
            if parameters_record.get("threads_effective") != shard.cores:
                raise CampaignSummaryError(
                    f"effective Threads mismatch in {shard.identifier}"
                )
            effective = parameters_record.get("profile_effective", {})
            if float(effective.get("TimeLimit", -1)) != 28800:
                raise CampaignSummaryError(
                    f"effective TimeLimit mismatch in {shard.identifier}"
                )

        energy = ENERGY.summarize_document(
            telemetry,
            required_runs=required_runs,
            required_configurations=1,
            workloads=[str(shard.workload)],
        )
        local_data = telemetry.get("data", {})
        for run in energy["runs"]:
            local_key = run["run"]
            raw = copy.deepcopy(local_data[local_key])
            repetition = run["configuration"]["repetition"]
            global_key = f"{shard.cores};{shard.input_index};{repetition}"
            if global_key in compact_data:
                raise CampaignSummaryError(f"duplicate merged run key: {global_key}")
            raw.pop("sensors", None)
            raw["rapl-sysfs"] = {
                "0": run["whole_program"]["sampled_energy_j"],
                **{
                    region_id: values["energy_j"]
                    for region_id, values in run["regions"].items()
                },
            }
            compact_data[global_key] = raw
            remapped = copy.deepcopy(run)
            remapped["run"] = global_key
            remapped["configuration"].update(
                {
                    "cores": shard.cores,
                    "input_index": shard.input_index,
                    "workload": str(shard.workload),
                }
            )
            all_valid_runs.append(remapped)
        for invalid in energy["invalid_runs"]:
            remapped = copy.deepcopy(invalid)
            repetition = remapped["configuration"]["repetition"]
            remapped["run"] = f"{shard.cores};{shard.input_index};{repetition}"
            remapped["configuration"].update(
                {
                    "cores": shard.cores,
                    "input_index": shard.input_index,
                    "workload": str(shard.workload),
                }
            )
            all_invalid_runs.append(remapped)

        metrics = [record["metrics"] for record in metadata]
        statuses = Counter(item["status_name"] for item in metrics)
        runtimes = [item["gurobi_runtime_s"] for item in metrics]
        gaps = [item["mip_gap"] for item in metrics if item.get("mip_gap") is not None]
        group = energy["configuration_groups"][0]
        configuration_records.append(
            {
                "cores": shard.cores,
                "input_index": shard.input_index,
                "workload": str(shard.workload),
                "attempted_runs": energy["attempted_run_count"],
                "valid_energy_runs": energy["run_count"],
                "status_counts": dict(sorted(statuses.items())),
                "median_gurobi_runtime_s": statistics.median(runtimes),
                "maximum_gurobi_runtime_s": max(runtimes),
                "median_mip_gap": statistics.median(gaps) if gaps else None,
                "maximum_mip_gap": max(gaps) if gaps else None,
                "median_energy_error_percent": group["accuracy"][
                    "median_absolute_error_percent"
                ],
                "region_0_cv_percent": group["variability"][
                    "region_0_cv_percent"
                ],
            }
        )
        shard_records.append(
            {
                "array_index": shard.array_index,
                "identifier": shard.identifier,
                "cores": shard.cores,
                "input_index": shard.input_index,
                "workload": str(shard.workload),
                "manifest": str(manifest_path.resolve()),
                "manifest_sha256": _sha256(manifest_path),
                "telemetry": str(telemetry_path.resolve()),
                "telemetry_sha256": _sha256(telemetry_path),
            }
        )

    if len(source_commits) != 1:
        raise CampaignSummaryError(
            f"shards do not share one source commit: {sorted(source_commits)}"
        )
    assert first_config is not None
    viewer_document = {
        "config": _compact_config(first_config, workloads),
        "data": dict(sorted(compact_data.items())),
    }
    viewer_path = campaign_root / "gurobi_hard_default_8h_viewer.json"
    viewer_path.write_text(
        json.dumps(viewer_document, separators=(",", ":"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    errors = [run["whole_program"]["absolute_error_percent"] for run in all_valid_runs]
    report = {
        "schema_version": 1,
        "campaign": "gurobi_hard_default_8h",
        "source_commit": next(iter(source_commits)),
        "profile": {
            "id": "default",
            "kind": "default",
            "gurobi_time_limit_seconds": 28800,
            "statement": (
                "Gurobi default profile with runner-controlled Threads, "
                "deterministic Seed=10000+input_index, and TimeLimit=28800"
            ),
        },
        "resources": [1, 2, 4],
        "repetitions": 6,
        "attempted_runs": 90,
        "valid_energy_runs": len(all_valid_runs),
        "invalid_energy_runs": all_invalid_runs,
        "configuration_count": len(configuration_records),
        "configurations": configuration_records,
        "energy_gate": {
            "median_absolute_error_percent": statistics.median(errors),
            "maximum_configuration_cv_percent": max(
                item["region_0_cv_percent"] for item in configuration_records
            ),
            "accuracy_accepted": all(
                item["median_energy_error_percent"] <= 5.0
                and item["valid_energy_runs"] >= required_runs
                for item in configuration_records
            ),
            "variability_preferred": all(
                item["region_0_cv_percent"] <= 10.0
                and item["valid_energy_runs"] >= required_runs
                for item in configuration_records
            ),
        },
        "shards": shard_records,
        "viewer_artifact": {
            "path": str(viewer_path.resolve()),
            "sha256": _sha256(viewer_path),
            "contains_raw_power_samples": False,
            "contains_only_valid_energy_runs": True,
        },
    }
    report_path = campaign_root / "campaign_summary.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_root", type=Path)
    parser.add_argument(
        "--config",
        type=Path,
        default=SCRIPT_DIR.parent / "experiments" / "gurobi-hard-default-8h.yaml",
    )
    parser.add_argument("--require-runs", type=int, default=5)
    arguments = parser.parse_args()
    try:
        report = summarize_campaign(
            config_path=arguments.config.expanduser().resolve(),
            campaign_root=arguments.campaign_root.expanduser().resolve(),
            required_runs=arguments.require_runs,
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        CampaignSummaryError,
        ENERGY.EnergySummaryError,
    ) as exc:
        print(f"validation_error={exc}", file=sys.stderr)
        return 2

    gate = report["energy_gate"]
    print(f"attempted_runs={report['attempted_runs']}")
    print(f"valid_energy_runs={report['valid_energy_runs']}")
    print(f"invalid_energy_runs={len(report['invalid_energy_runs'])}")
    print(f"configuration_count={report['configuration_count']}")
    print(
        "median_absolute_error_percent="
        f"{gate['median_absolute_error_percent']:.6f}"
    )
    print(
        "maximum_configuration_cv_percent="
        f"{gate['maximum_configuration_cv_percent']:.6f}"
    )
    print(f"accuracy_accepted={gate['accuracy_accepted']}")
    print(f"variability_preferred={gate['variability_preferred']}")
    print(f"summary={(arguments.campaign_root / 'campaign_summary.json').resolve()}")
    print(
        "viewer_artifact="
        f"{report['viewer_artifact']['path']}"
    )
    return 0 if gate["accuracy_accepted"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
