import subprocess
import sys
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR / "src"))

from pascalpy.adapters.gurobi_adapter import GurobiFileAdapter  # noqa: E402
from pascalpy.experiment_profiles import (  # noqa: E402
    SolverName,
    SolverProfile,
    default_solver_profile,
)


class EnvironmentPolicy:
    def __init__(self, configuration: dict):
        self.track_energy_rapl = configuration.get("track_energy_rapl")
        self.track_cores = configuration.get("track_cores", False)
        self.idle_time_seconds = configuration.get("idle_time_seconds", 0)


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


def main():
    yaml_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path("meu_experimento.yaml")
    )
    with yaml_path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)

    experiment = config["experiment"]
    solver = SolverName(experiment.get("solver", SolverName.GUROBI.value))
    if solver != SolverName.GUROBI:
        raise NotImplementedError(
            f"Solver {solver.value!r} is reserved for a subsequent sprint"
        )

    profiles, profiles_declared = _load_profiles(experiment)
    output_root = Path(config["output"]["directory"])
    output_root.mkdir(parents=True, exist_ok=True)

    cores = experiment["resources"]
    workloads = [Path(workload) for workload in experiment["workloads"]]
    repetitions = experiment["repetitions"]
    environment = EnvironmentPolicy(config.get("environment", {}))

    for profile in profiles:
        if profiles_declared:
            output_dir = output_root / solver.value / profile.id
            experiment_name = f"{experiment['name']}_{solver.value}_{profile.id}"
        else:
            output_dir = output_root
            experiment_name = experiment["name"]
        output_dir.mkdir(parents=True, exist_ok=True)

        adapter = GurobiFileAdapter(profile=profile)
        command = adapter.build_batch_command(
            exp_name=experiment_name,
            cores_list=cores,
            workloads_list=workloads,
            repetitions=repetitions,
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


if __name__ == "__main__":
    main()


