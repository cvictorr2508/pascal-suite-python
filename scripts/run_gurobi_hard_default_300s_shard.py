InvalidOperation: 
Line |
   2 |  [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); Ge .
     |  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
     | Cannot create type. Only core types are supported in this language mode.
#!/usr/bin/env python3
"""Run one instance/thread shard of the bounded Gurobi validation campaign."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ShardConfigurationError(ValueError):
    """Raised when the canonical campaign cannot be safely sharded."""


@dataclass(frozen=True)
class CampaignShard:
    """One resource/workload combination executed for all repetitions."""

    array_index: int
    cores: int
    input_index: int
    workload: Path

    @property
    def identifier(self) -> str:
        return f"c{self.cores}_i{self.input_index}"


def load_configuration(path: Path) -> dict[str, Any]:
    """Load a YAML mapping."""

    with path.open("r", encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    if not isinstance(document, dict):
        raise ShardConfigurationError("Campaign configuration must be a mapping")
    return document


def campaign_shards(configuration: dict[str, Any]) -> list[CampaignShard]:
    """Validate the campaign contract and return deterministic shards."""

    experiment = configuration.get("experiment")
    if not isinstance(experiment, dict):
        raise ShardConfigurationError("Missing experiment mapping")
    if experiment.get("solver") != "gurobi":
        raise ShardConfigurationError("Campaign solver must be gurobi")
    if experiment.get("scaling_mode") != "strong":
        raise ShardConfigurationError("Campaign scaling_mode must be strong")
    if experiment.get("repetitions") != 6:
        raise ShardConfigurationError("Campaign must declare exactly six repetitions")

    resources = experiment.get("resources")
    if resources != [1, 2, 4]:
        raise ShardConfigurationError("Campaign resources must be [1, 2, 4]")
    workloads = experiment.get("workloads")
    if not isinstance(workloads, list) or len(workloads) != 5:
        raise ShardConfigurationError("Campaign must declare five workloads")
    expected_names = [
        f"CFL_hard_instance_{value}.lp.gz" for value in (5, 10, 15, 20, 25)
    ]
    observed_names = [Path(item).name for item in workloads]
    if observed_names != expected_names:
        raise ShardConfigurationError(
            f"Unexpected workload order: {observed_names}; expected {expected_names}"
        )

    profiles = experiment.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != 1:
        raise ShardConfigurationError("Campaign must declare one profile")
    profile = profiles[0]
    if profile.get("id") != "default" or profile.get("kind") != "default":
        raise ShardConfigurationError("Campaign profile must be default/default")
    if profile.get("objective_sense") != "minimize":
        raise ShardConfigurationError(
            "Campaign must explicitly force objective_sense=minimize"
        )
    parameters = profile.get("parameters")
    if parameters != {"TimeLimit": 300}:
        raise ShardConfigurationError(
            "Default campaign may set only Gurobi TimeLimit=300"
        )

    shards = []
    for cores in resources:
        for input_index, workload in enumerate(workloads):
            shards.append(
                CampaignShard(
                    array_index=len(shards),
                    cores=cores,
                    input_index=input_index,
                    workload=Path(workload).expanduser().resolve(),
                )
            )
    return shards


def build_shard_configuration(
    configuration: dict[str, Any],
    shard: CampaignShard,
    campaign_root: Path,
) -> dict[str, Any]:
    """Build the single-configuration YAML consumed by the existing runner."""

    derived = copy.deepcopy(configuration)
    experiment = derived["experiment"]
    experiment["name"] = f"{experiment['name']}_{shard.identifier}"
    experiment["resources"] = [shard.cores]
    experiment["workloads"] = [str(shard.workload)]
    derived["output"]["directory"] = str(
        (campaign_root / "shards" / shard.identifier).resolve()
    )
    return derived


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "experiments" / "gurobi-hard-default-300s.yaml",
    )
    parser.add_argument("--array-index", type=int)
    parser.add_argument("--campaign-root", type=Path)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--check-inputs", action="store_true")
    arguments = parser.parse_args()

    config_path = arguments.config.expanduser().resolve()
    configuration = load_configuration(config_path)
    shards = campaign_shards(configuration)
    if arguments.check_inputs:
        missing = [
            str(shard.workload)
            for shard in shards[:5]
            if not shard.workload.is_file() or shard.workload.stat().st_size == 0
        ]
        if missing:
            raise SystemExit(f"missing or empty workloads: {missing}")
        print("workload_preflight=accepted count=5")
        return 0
    if arguments.describe:
        print(
            json.dumps(
                [
                    {
                        "array_index": shard.array_index,
                        "cores": shard.cores,
                        "input_index": shard.input_index,
                        "workload": str(shard.workload),
                    }
                    for shard in shards
                ],
                indent=2,
            )
        )
        return 0
    if arguments.array_index is None:
        raise SystemExit(
            "--array-index is required unless --describe or --check-inputs is used"
        )
    if not 0 <= arguments.array_index < len(shards):
        raise SystemExit(
            f"array index must be between 0 and {len(shards) - 1}: "
            f"{arguments.array_index}"
        )

    shard = shards[arguments.array_index]
    campaign_root = arguments.campaign_root
    if campaign_root is None:
        raw_root = os.environ.get("PASCAL_CAMPAIGN_ROOT")
        campaign_root = (
            Path(raw_root)
            if raw_root
            else Path(configuration["output"]["directory"])
        )
    campaign_root = campaign_root.expanduser().resolve()
    shard_root = campaign_root / "shards" / shard.identifier
    if shard_root.exists() and any(shard_root.iterdir()):
        raise SystemExit(f"refusing to overwrite nonempty shard: {shard_root}")

    config_directory = campaign_root / "_configs"
    config_directory.mkdir(parents=True, exist_ok=True)
    derived_path = config_directory / f"{shard.identifier}.yaml"
    derived = build_shard_configuration(configuration, shard, campaign_root)
    derived_path.write_text(
        yaml.safe_dump(derived, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )

    os.environ["PASCAL_GLOBAL_INPUT_INDEX"] = str(shard.input_index)
    print(f"campaign_root={campaign_root}")
    print(f"array_index={shard.array_index}")
    print(f"shard={shard.identifier}")
    print(f"cores={shard.cores}")
    print(f"input_index={shard.input_index}")
    print(f"workload={shard.workload}")
    print("repetitions=6")
    print("gurobi_time_limit_seconds=300")
    sys.path.insert(0, str(ROOT / "src"))
    from pascalpy.cli import run_configuration

    manifest_path = run_configuration(derived_path)
    print(f"shard_manifest={manifest_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

