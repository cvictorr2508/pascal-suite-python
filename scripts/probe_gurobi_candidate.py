#!/usr/bin/env python3
"""Measure one MILP candidate before running the full PaScal experiment."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUS_NAMES = (
    "LOADED", "OPTIMAL", "INFEASIBLE", "INF_OR_UNBD", "UNBOUNDED",
    "CUTOFF", "ITERATION_LIMIT", "NODE_LIMIT", "TIME_LIMIT",
    "SOLUTION_LIMIT", "INTERRUPTED", "NUMERIC", "SUBOPTIMAL",
    "INPROGRESS", "USER_OBJ_LIMIT", "WORK_LIMIT", "MEM_LIMIT",
)


def _safe_get(model: Any, attribute: str, default: Any = None) -> Any:
    try:
        return getattr(model, attribute)
    except Exception:
        return default


def _finite_float(value: Any) -> float | None:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _status_name(gurobi: Any, status: int | None) -> str:
    if status is None:
        return "UNKNOWN"
    for name in STATUS_NAMES:
        if getattr(gurobi.GRB, name, None) == status:
            return name
    return f"STATUS_{status}"

def _peak_rss_kib() -> float | None:
    try:
        import resource
    except ImportError:
        return None

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return float(peak) / 1024.0
    return float(peak)


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    os.replace(temporary, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Load and optimize one Gurobi model with bounded resources, writing "
            "a machine-readable JSON report."
        )
    )
    parser.add_argument("--workload", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--seed", type=int, default=10000)
    parser.add_argument(
        "--gurobi-output",
        action="store_true",
        help="Keep the Gurobi solver log enabled in the SLURM output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.threads < 1:
        raise SystemExit("--threads must be at least 1")
    if args.time_limit <= 0:
        raise SystemExit("--time-limit must be positive")

    workload = args.workload.expanduser().resolve(strict=True)
    output_path = args.output_dir.resolve() / f"probe_{workload.stem}.json"
    started_wall = time.perf_counter()
    document: dict[str, Any] = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "workload": str(workload),
        "file_size_bytes": workload.stat().st_size,
        "parameters": {
            "threads": args.threads,
            "time_limit_s": args.time_limit,
            "seed": args.seed,
        },
        "metrics": {},
    }

    environment = None
    model = None
    exit_code = 0
    try:
        import gurobipy as gp

        environment = gp.Env(empty=True)
        environment.setParam("OutputFlag", int(args.gurobi_output))
        environment.start()

        read_started = time.perf_counter()
        model = gp.read(str(workload), env=environment)
        read_wall_s = time.perf_counter() - read_started

        model.Params.Threads = args.threads
        model.Params.Seed = args.seed
        model.Params.TimeLimit = args.time_limit

        optimize_started = time.perf_counter()
        model.optimize()
        optimize_wall_s = time.perf_counter() - optimize_started

        status = int(_safe_get(model, "Status", 0))
        solution_count = int(_safe_get(model, "SolCount", 0))
        document["model"] = {
            "variables": int(_safe_get(model, "NumVars", 0)),
            "constraints": int(_safe_get(model, "NumConstrs", 0)),
            "binary_variables": int(_safe_get(model, "NumBinVars", 0)),
            "integer_variables": int(_safe_get(model, "NumIntVars", 0)),
            "nonzeros": int(_safe_get(model, "NumNZs", 0)),
        }
        document["metrics"] = {
            "read_wall_s": read_wall_s,
            "optimize_wall_s": optimize_wall_s,
            "gurobi_runtime_s": _finite_float(_safe_get(model, "Runtime")),
            "status": status,
            "status_name": _status_name(gp, status),
            "solution_count": solution_count,
            "node_count": _finite_float(_safe_get(model, "NodeCount")),
            "work": _finite_float(_safe_get(model, "Work")),
            "objective": (
                _finite_float(_safe_get(model, "ObjVal"))
                if solution_count > 0 else None
            ),
            "mip_gap": (
                _finite_float(_safe_get(model, "MIPGap"))
                if solution_count > 0 else None
            ),
        }
    except Exception as exc:
        exit_code = 1
        document["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if model is not None:
            model.dispose()
        if environment is not None:
            environment.dispose()
        document["total_wall_s"] = time.perf_counter() - started_wall
        document["peak_rss_kib"] = _peak_rss_kib()
        _write_json(output_path, document)

    print(json.dumps(document, indent=2, sort_keys=True, allow_nan=False))
    print(f"report={output_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
