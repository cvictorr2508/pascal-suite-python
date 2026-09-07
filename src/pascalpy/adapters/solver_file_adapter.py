"""Shared PaScal Analyzer adapter for file-based solver runners."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pascalpy.experiment_profiles import (
    SolverName,
    SolverProfile,
    default_solver_profile,
)
from pascalpy.instrumentation.proxy_builder import (
    build_region_proxy,
    resolve_pascal_ops_library,
)


class SolverFileAdapter:
    """Build one PaScal Analyzer batch for a validated solver profile."""

    def __init__(
        self,
        *,
        solver: SolverName,
        runner_name: str,
        profile: SolverProfile | None = None,
        legacy_parameters: dict | None = None,
    ):
        if profile is not None and legacy_parameters:
            raise ValueError("Use either profile or legacy parameters, not both")
        self.solver = solver
        self.runner_name = runner_name
        self.profile = profile or default_solver_profile()
        if legacy_parameters:
            self.profile = self.profile.model_copy(
                update={"parameters": legacy_parameters}
            )

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
        workloads_str_list = [str(workload.resolve()) for workload in workloads_list]

        base_config = {
            "experiment_name": exp_name,
            "solver": self.solver.value,
            "profile": self._profile_payload(),
            "output_dir": str(output_dir.resolve()),
            "workloads_list": workloads_str_list,
        }
        with base_config_path.open("w", encoding="utf-8") as stream:
            json.dump(base_config, stream, indent=2)

        runner_path = Path(__file__).parent.parent / "runners" / self.runner_name
        proxy_path = build_region_proxy(
            output_dir,
            name=f"{run_id}_region_proxy",
        )
        pascal_library = resolve_pascal_ops_library().resolve()

        command = [
            "env",
            f"PASCAL_PROXY_PYTHON_BIN={sys.executable}",
            f"PASCAL_PROXY_RUNNER={runner_path.resolve()}",
            f"PASCAL_PROXY_BASE_CONFIG={base_config_path.resolve()}",
            f"PASCAL_OPS_LIB={pascal_library}",
            "pascalanalyzer",
            "-c",
            ",".join(map(str, cores_list)),
            "-i",
            ",".join(workloads_str_list),
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
                command.extend(["--rple", rapl_backend, "--rpls", rapl_backend])
            if getattr(env_policy, "track_cores", False):
                command.append("--prcs")
            if getattr(env_policy, "idle_time_seconds", 0) > 0:
                command.extend(
                    ["--idtm", str(int(env_policy.idle_time_seconds))]
                )

        command.append(str(proxy_path.resolve()))
        return command
