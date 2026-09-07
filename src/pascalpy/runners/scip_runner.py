"""Execute one SCIP workload with canonical PaScal regions."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[2]))

from pascalpy.instrumentation.pascalops import (  # noqa: E402
    instrumentation_status,
    pascal_region,
)
from pascalpy.instrumentation.solver_regions import (  # noqa: E402
    MODEL_BUILD_REGION_ID,
    SOLVE_EXECUTION_REGION_ID,
    SOLVER_PIPELINE_REGION_ID,
    solver_region_schema,
)

try:
    from pyscipopt import Model, SCIP_PARAMSETTING
except ImportError:
    Model = None
    SCIP_PARAMSETTING = None


def _current_affinity() -> list[int] | None:
    if not hasattr(os, "sched_getaffinity"):
        return None
    try:
        return sorted(os.sched_getaffinity(0))
    except OSError:
        return None


def _safe_call(model: Any, method_name: str, default=None):
    try:
        return getattr(model, method_name)()
    except Exception:
        return default


def _resolve_initial_solution(
    profile: dict, workload: Path
) -> tuple[Path | None, bool]:
    specification = profile.get("initial_solution")
    if not isinstance(specification, dict):
        return None, False

    files = specification.get("files")
    if not isinstance(files, dict):
        files = {}
    candidates = (str(workload.resolve()), str(workload), workload.name)
    for candidate in candidates:
        if candidate in files:
            return Path(files[candidate]).expanduser().resolve(), bool(
                specification.get("required", True)
            )
    return None, bool(specification.get("required", True))


def _json_solution(model: Any, solution_path: Path):
    with solution_path.open("r", encoding="utf-8") as stream:
        document = json.load(stream)
    values = document.get("values") if isinstance(document, dict) else None
    if values is None and isinstance(document, dict):
        values = document
    if not isinstance(values, dict) or not values:
        raise ValueError(
            "A JSON warm start must contain a non-empty variable-to-value mapping"
        )

    variables = {variable.name: variable for variable in model.getVars()}
    solution = model.createPartialSol()
    assigned = 0
    for variable_name, raw_value in values.items():
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise ValueError(f"Invalid warm-start value for {variable_name!r}")
        value = float(raw_value)
        if not math.isfinite(value):
            raise ValueError(f"Non-finite warm-start value for {variable_name!r}")
        variable = variables.get(str(variable_name))
        if variable is None:
            raise ValueError(f"Warm-start variable not found: {variable_name}")
        model.setSolVal(solution, variable, value)
        assigned += 1
    return solution, assigned


def _apply_profile(model: Any, workload: Path, profile: dict) -> dict:
    profile_id = str(profile.get("id", "default"))
    profile_kind = str(profile.get("kind", "default"))
    requested_parameters = dict(profile.get("parameters") or {})
    effective_parameters = {}

    if profile_kind == "presolve-off":
        conflicting = sorted(
            name for name in requested_parameters if name.startswith("presolving/")
        )
        if conflicting:
            raise ValueError(
                "The presolve-off profile cannot override presolving parameters: "
                f"{conflicting}"
            )
        setting = (
            SCIP_PARAMSETTING.OFF
            if SCIP_PARAMSETTING is not None
            else "off"
        )
        model.setPresolve(setting)
        effective_parameters["presolve"] = "off"

    for name, value in requested_parameters.items():
        model.setParam(name, value)
        effective_parameters[name] = model.getParam(name)

    initial_solution = {
        "requested": profile_kind == "warm-start",
        "applied": False,
        "accepted": None,
        "path": None,
        "format": None,
        "variables_assigned": 0,
    }
    if profile_kind == "warm-start":
        solution_path, required = _resolve_initial_solution(profile, workload)
        if solution_path is None:
            if required:
                raise FileNotFoundError(
                    f"No initial solution is mapped to workload {workload.name}"
                )
        elif not solution_path.is_file():
            if required:
                raise FileNotFoundError(
                    f"Initial solution does not exist: {solution_path}"
                )
        else:
            suffix = solution_path.suffix.lower()
            if suffix == ".sol":
                solution = model.readSolFile(str(solution_path))
                assigned = 0
            elif suffix == ".json":
                solution, assigned = _json_solution(model, solution_path)
            else:
                raise ValueError(
                    "SCIP warm starts must use .sol or a JSON "
                    "variable-to-value mapping"
                )
            accepted = bool(model.addSol(solution, free=True))
            if required and not accepted:
                raise RuntimeError(
                    f"SCIP rejected required initial solution: {solution_path}"
                )
            initial_solution.update(
                {
                    "applied": True,
                    "accepted": accepted,
                    "path": str(solution_path),
                    "format": suffix.removeprefix("."),
                    "variables_assigned": assigned,
                }
            )

    return {
        "id": profile_id,
        "kind": profile_kind,
        "parameters_requested": requested_parameters,
        "parameters_effective": effective_parameters,
        "initial_solution": initial_solution,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-config", required=True)
    parser.add_argument("--workload", required=True)
    arguments = parser.parse_args()

    if Model is None:
        raise RuntimeError("PySCIPOpt is not available in the runner environment")

    base_config_path = Path(arguments.base_config)
    with base_config_path.open("r", encoding="utf-8") as stream:
        base_config = json.load(stream)

    cores = int(os.environ.get("OMP_NUM_THREADS", "1"))
    if cores != 1:
        raise RuntimeError(
            "The PySCIPOpt optimize() path is serial; SCIP experiments currently "
            "require exactly one core"
        )

    workload = Path(arguments.workload).resolve()
    workload_str = str(workload)
    try:
        input_idx = base_config["workloads_list"].index(workload_str)
    except ValueError:
        input_idx = 0

    start_timestamp = time.time()
    meta_path = (
        Path(base_config["output_dir"])
        / f"meta_c{cores}_i{input_idx}_{int(start_timestamp * 1000)}.json"
    )

    affinity_before = _current_affinity()
    if affinity_before is not None and hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {affinity_before[0]})
    affinity_effective = _current_affinity()
    pascal_status = instrumentation_status()
    profile = dict(base_config.get("profile") or {})
    seed = 10000 + input_idx

    metadata = {
        "workload": workload_str,
        "cores": cores,
        "input_idx": input_idx,
        "start_timestamp": start_timestamp,
        "cpu_affinity": affinity_effective,
        "solver": "scip",
        "profile": {
            "id": str(profile.get("id", "default")),
            "kind": str(profile.get("kind", "default")),
        },
        "pascal_instrumentation": {
            "requested": True,
            "available": pascal_status["available"],
            "backend": pascal_status.get("backend"),
            "library_path": pascal_status["library_path"],
            "start_symbol": pascal_status["start_symbol"],
            "stop_symbol": pascal_status["stop_symbol"],
            "proxy_command_fd": pascal_status.get("proxy_command_fd"),
            "proxy_ack_fd": pascal_status.get("proxy_ack_fd"),
            "region_schema": solver_region_schema(),
        },
        "parameters": {
            "threads_requested": cores,
            "threads_effective": 1,
            "parallelism_mode": "serial",
            "seed_requested": seed,
            "seed_effective": None,
            "profile_requested": {},
            "profile_effective": {},
        },
        "initial_solution": {},
        "metrics": {},
    }

    model = None
    read_wall_s = 0.0
    solve_wall_s = 0.0
    try:
        pipeline_line = sys._getframe().f_lineno + 2
        with pascal_region(
            SOLVER_PIPELINE_REGION_ID,
            filename=Path(__file__).name,
            start_line=pipeline_line,
            stop_line=pipeline_line,
        ):
            build_line = sys._getframe().f_lineno + 2
            with pascal_region(
                MODEL_BUILD_REGION_ID,
                filename=Path(__file__).name,
                start_line=build_line,
                stop_line=build_line,
            ):
                read_started = time.perf_counter()
                model = Model()
                model.hideOutput()
                model.readProblem(str(workload))
                read_wall_s = time.perf_counter() - read_started

            model.setIntParam("randomization/randomseedshift", seed)
            applied_profile = _apply_profile(model, workload, profile)
            metadata["parameters"].update(
                {
                    "seed_effective": int(
                        model.getParam("randomization/randomseedshift")
                    ),
                    "profile_requested": applied_profile["parameters_requested"],
                    "profile_effective": applied_profile["parameters_effective"],
                }
            )
            metadata["initial_solution"] = applied_profile["initial_solution"]

            solve_line = sys._getframe().f_lineno + 2
            with pascal_region(
                SOLVE_EXECUTION_REGION_ID,
                filename=Path(__file__).name,
                start_line=solve_line,
                stop_line=solve_line,
            ):
                solve_started = time.perf_counter()
                model.optimize()
                solve_wall_s = time.perf_counter() - solve_started

        solution_count = int(model.getNSols())
        metadata["metrics"] = {
            "status": str(model.getStatus()),
            "read_wall_clock_s": read_wall_s,
            "scip_solving_time_s": _safe_call(model, "getSolvingTime"),
            "solve_wall_clock_s": solve_wall_s,
            "node_count": _safe_call(model, "getNNodes"),
            "gap": _safe_call(model, "getGap"),
            "objective": (
                float(model.getObjVal()) if solution_count > 0 else None
            ),
            "solution_count": solution_count,
        }
    except Exception as exc:
        metadata["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        raise
    finally:
        if model is not None:
            model.freeProb()
        with meta_path.open("w", encoding="utf-8") as stream:
            json.dump(metadata, stream, indent=2)


if __name__ == "__main__":
    main()
