"""Create a Gurobi MIP-start artifact outside the measured experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import gurobipy as gp


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_warm_start(
    workload: Path,
    output: Path,
    *,
    threads: int,
    seed: int,
    time_limit_s: float | None,
) -> Path:
    workload = workload.expanduser().resolve()
    output = output.expanduser().resolve()
    if not workload.is_file():
        raise FileNotFoundError(f"Workload does not exist: {workload}")
    if output.suffix.lower() != ".mst":
        raise ValueError("The output path must use the .mst extension")
    output.parent.mkdir(parents=True, exist_ok=True)

    model = gp.read(str(workload))
    started = time.perf_counter()
    try:
        model.setParam("Threads", threads)
        model.setParam("Seed", seed)
        if time_limit_s is not None:
            model.setParam("TimeLimit", time_limit_s)
        model.optimize()
        elapsed = time.perf_counter() - started
        if model.SolCount < 1:
            raise RuntimeError(
                "Gurobi did not find a feasible solution; no MIP start was written"
            )
        model.write(str(output))
        metadata = {
            "schema_version": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "unmeasured-warm-start-preparation",
            "workload": {
                "path": str(workload),
                "size_bytes": workload.stat().st_size,
                "sha256": _sha256(workload),
            },
            "warm_start": {
                "path": str(output),
                "size_bytes": output.stat().st_size,
                "sha256": _sha256(output),
            },
            "runtime": {
                "python_version": platform.python_version(),
                "gurobi_version": ".".join(map(str, gp.gurobi.version())),
                "elapsed_s": elapsed,
            },
            "parameters": {
                "Threads": threads,
                "Seed": seed,
                "TimeLimit": time_limit_s,
            },
            "solution": {
                "status": int(model.Status),
                "objective": float(model.ObjVal),
                "solution_count": int(model.SolCount),
            },
        }
    finally:
        model.dispose()

    metadata_path = output.with_suffix(output.suffix + ".json")
    with metadata_path.open("w", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2)
    return metadata_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Solve an instance and export a checksummed Gurobi .mst file."
    )
    parser.add_argument("workload", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--seed", type=int, default=10000)
    parser.add_argument("--time-limit", type=float, default=None)
    arguments = parser.parse_args()
    if arguments.threads < 1:
        parser.error("--threads must be at least 1")
    if arguments.time_limit is not None and arguments.time_limit <= 0:
        parser.error("--time-limit must be positive")

    metadata_path = export_warm_start(
        arguments.workload,
        arguments.output,
        threads=arguments.threads,
        seed=arguments.seed,
        time_limit_s=arguments.time_limit,
    )
    print(f"warm_start_metadata={metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

