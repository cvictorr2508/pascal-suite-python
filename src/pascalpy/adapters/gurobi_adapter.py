import json
import sys
from pathlib import Path

from pascalpy.experiment_profiles import SolverProfile, default_solver_profile
from pascalpy.instrumentation.proxy_builder import (
    build_region_proxy,
    resolve_pascal_ops_library,
)


class GurobiFileAdapter:
    """Build one PaScal Analyzer batch for a validated Gurobi profile."""

    def __init__(
        self,
        profile: SolverProfile | None = None,
        limits: dict | None = None,
    ):
        if profile is not None and limits:
            raise ValueError("Use either profile or legacy limits, not both")
        self.profile = profile or default_solver_profile()
        if limits:
            self.profile = self.profile.model_copy(update={"parameters": limits})

    def _profile_payload(self) -> dict:
        payload = self.profile.model_dump(mode="json")
        initial_solution = payload.get("initial_solution")
        if isinstance(initial_solution, dict):
            initial_solution["files"] = {
                key: str(Path(value).expanduser().resolve())
                for key, value in initial_solution["files"].items()
            }
        return payload

    def build_batch_command(
        self,
        exp_name: str,
        cores_list: list,
        workloads_list: list,
        repetitions: int,
        output_dir: Path,
        env_policy=None,
    ):
        run_id = f"exp_{exp_name}_batch"
        pascal_telemetry = output_dir / f"{run_id}_pascal.json"
        base_config_path = output_dir / "base_config.json"

        workloads_str_list = [str(w.resolve()) for w in workloads_list]

        base_config = {
            "experiment_name": exp_name,
            "solver": "gurobi",
            "profile": self._profile_payload(),
            "output_dir": str(output_dir.resolve()),
            "workloads_list": workloads_str_list,
        }
        with base_config_path.open("w", encoding="utf-8") as stream:
            json.dump(base_config, stream, indent=2)

        cores_arg = ",".join(map(str, cores_list))
        inputs_arg = ",".join(workloads_str_list)

        runner_path = Path(__file__).parent.parent / "runners" / "gurobi_runner.py"
        proxy_path = build_region_proxy(
            output_dir,
            name=f"{run_id}_region_proxy",
        )
        pascal_library = resolve_pascal_ops_library().resolve()

        base_cmd = [
            "env",
            f"PASCAL_PROXY_PYTHON_BIN={sys.executable}",
            f"PASCAL_PROXY_RUNNER={runner_path.resolve()}",
            f"PASCAL_PROXY_BASE_CONFIG={base_config_path.resolve()}",
            f"PASCAL_OPS_LIB={pascal_library}",
            "pascalanalyzer",
            "-c",
            cores_arg,
            "-i",
            inputs_arg,
            "-r",
            str(repetitions),
            "-t",
            "man",
            "--outp",
            str(pascal_telemetry.resolve()),
        ]

        if env_policy:
            if getattr(env_policy, "track_energy_rapl", None):
                rapl_backend = str(env_policy.track_energy_rapl)
                base_cmd.extend(
                    ["--rple", rapl_backend, "--rpls", rapl_backend]
                )
            if getattr(env_policy, "track_cores", False):
                base_cmd.append("--prcs")
            if getattr(env_policy, "idle_time_seconds", 0) > 0:
                base_cmd.extend(
                    ["--idtm", str(int(env_policy.idle_time_seconds))]
                )

        base_cmd.append(str(proxy_path.resolve()))
        return base_cmd

