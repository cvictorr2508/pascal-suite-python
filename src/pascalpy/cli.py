"""Command-line orchestration for reproducible PaScal solver experiments."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from pascalpy.adapters.gurobi_adapter import GurobiFileAdapter
from pascalpy.experiment_profiles import (
    ProfileKind,
    SolverName,
    SolverProfile,
    default_solver_profile,
)


class EnvironmentPolicy:
    """PaScal Analyzer telemetry options read from the YAML contract."""

    def __init__(self, configuration: dict):
        self.track_energy_rapl = configuration.get("track_energy_rapl")
        self.track_cores = configuration.get("track_cores", False)
        self.idle_time_seconds = configuration.get("idle_time_seconds", 0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(project_root: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _load_profiles(experiment: dict) -> tuple[list[SolverProfile], bool]:
    raw_profiles = experiment.get("profiles")
    if raw_profiles is None:
        return [default_solver_profile()], False
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ValueError("experiment.profiles must be a non-empty list")

    profiles = [SolverProfile.model_validate(profile) for profile in raw_profiles]
    profile_ids = [profile.id for profile in profiles]
    if len(profile_ids) != len(set(profile_ids)):
        raise ValueError("experiment.profiles contains duplicate profile IDs")
    return profiles, True


def _file_record(path: Path) -> dict:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Required research input does not exist: {resolved}")
    return {
        "path": str(resolved),
        "size_bytes": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def _initial_solution_records(
    profiles: list[SolverProfile], workloads: list[Path]
) -> list[dict]:
    records = []
    for profile in profiles:
        if profile.kind != ProfileKind.WARM_START:
            continue
        specification = profile.initial_solution
        if specification is None:
            continue
        for workload in workloads:
            solution = specification.resolve_for(workload)
            if solution is None:
                if specification.required:
                    raise FileNotFoundError(
                        "No initial solution is mapped to workload "
                        f"{workload.name} in profile {profile.id}"
                    )
                continue
            try:
                record = _file_record(solution)
            except FileNotFoundError:
                if specification.required:
                    raise
                continue
            record.update(
                {
                    "profile_id": profile.id,
                    "workload": str(workload.resolve()),
                }
            )
            records.append(record)
    return records


def build_research_manifest(
    *,
    config_path: Path,
    configuration: dict,
    profiles: list[SolverProfile],
    project_root: Path,
) -> dict:
    """Build a checksummed description of code, data, runtime, and treatments."""

    experiment = configuration["experiment"]
    workloads = [Path(item).expanduser().resolve() for item in experiment["workloads"]]
    status = _git_value(project_root, "status", "--porcelain", "--untracked-files=no")
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": _file_record(config_path),
        "source": {
            "git_commit": _git_value(project_root, "rev-parse", "HEAD"),
            "tracked_worktree_clean": status == "" if status is not None else None,
        },
        "runtime": {
            "hostname": socket.getfqdn(),
            "platform": platform.platform(),
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "packages": {
                "gurobipy": _distribution_version("gurobipy"),
                "pydantic": _distribution_version("pydantic"),
                "PyYAML": _distribution_version("PyYAML"),
                "PySCIPOpt": _distribution_version("PySCIPOpt"),
            },
        },
        "experiment": {
            "name": experiment["name"],
            "solver": experiment.get("solver", SolverName.GUROBI.value),
            "resources": experiment["resources"],
            "repetitions": experiment["repetitions"],
            "profiles": [profile.model_dump(mode="json") for profile in profiles],
        },
        "workloads": [_file_record(workload) for workload in workloads],
        "initial_solutions": _initial_solution_records(profiles, workloads),
        "slurm": {
            key: value
            for key in (
                "SLURM_JOB_ID",
                "SLURM_JOB_NAME",
                "SLURM_JOB_PARTITION",
                "SLURM_CPUS_PER_TASK",
                "SLURM_JOB_NODELIST",
            )
            if (value := os.environ.get(key)) is not None
        },
    }


def run_configuration(config_path: Path) -> Path:
    """Validate and run every profile declared in one YAML configuration."""

    config_path = config_path.expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as stream:
        configuration = yaml.safe_load(stream)

    experiment = configuration["experiment"]
    solver = SolverName(experiment.get("solver", SolverName.GUROBI.value))
    if solver != SolverName.GUROBI:
        raise NotImplementedError(
            f"Solver {solver.value!r} is reserved for the SCIP sprint"
        )

    profiles, profiles_declared = _load_profiles(experiment)
    output_root = Path(configuration["output"]["directory"])
    output_root.mkdir(parents=True, exist_ok=True)
    project_root = Path.cwd().resolve()

    manifest = build_research_manifest(
        config_path=config_path,
        configuration=configuration,
        profiles=profiles,
        project_root=project_root,
    )
    manifest_path = output_root / "research_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)

    workloads = [Path(workload) for workload in experiment["workloads"]]
    environment = EnvironmentPolicy(configuration.get("environment", {}))
    for profile in profiles:
        if profiles_declared:
            output_dir = output_root / solver.value / profile.id
            experiment_name = f"{experiment['name']}_{solver.value}_{profile.id}"
        else:
            output_dir = output_root
            experiment_name = experiment["name"]
        output_dir.mkdir(parents=True, exist_ok=True)

        command = GurobiFileAdapter(profile=profile).build_batch_command(
            exp_name=experiment_name,
            cores_list=experiment["resources"],
            workloads_list=workloads,
            repetitions=experiment["repetitions"],
            output_dir=output_dir,
            env_policy=environment,
        )
        print(
            f"=== RUNNING SOLVER={solver.value} PROFILE={profile.id} ===",
            flush=True,
        )
        print("Executing:", " ".join(map(str, command)), flush=True)
        subprocess.run(command, check=True)
        print(
            f"=== COMPLETED SOLVER={solver.value} PROFILE={profile.id} ===",
            flush=True,
        )
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a reproducible PaScal solver experiment matrix."
    )
    parser.add_argument("configuration", type=Path, help="Experiment YAML file")
    arguments = parser.parse_args(argv)
    manifest_path = run_configuration(arguments.configuration)
    print(f"research_manifest={manifest_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

