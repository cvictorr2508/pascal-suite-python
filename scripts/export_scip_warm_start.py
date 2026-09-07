"""Create a SCIP solution artifact outside the measured experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from pyscipopt import Model


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
    seed: int,
    time_limit_s: float | None,
) -> Path:
    workload = workload.expanduser().resolve()
    output = output.expanduser().resolve()
    if not workload.is_file():
        raise FileNotFoundError(f"Workload does not exist: {workload}")
    if output.suffix.lower() != ".sol":
        raise ValueError("The output path must use the .sol extension")
    output.parent.mkdir(parents=True, exist_ok=True)

    model = Model()
    started = time.perf_counter()
    try:
        model.hideOutput()
        model.readProblem(str(workload))
        model.setIntParam("randomization/randomseedshift", seed)
        if time_limit_s is not None:
            model.setRealParam("limits/time", time_limit_s)
        model.optimize()
        elapsed = time.perf_counter() - started
        solution = model.getBestSol()
        if solution is None:
            raise RuntimeError(
                "SCIP did not find a feasible solution; no warm start was written"
            )
        model.writeSol(
            solution,
            filename=str(output),
            write_zeros=True,
        )
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
                "pyscipopt_version": __import__("pyscipopt").__version__,
                "scip_version": str(model.version()),
                "elapsed_s": elapsed,
            },
            "parameters": {
                "threads_requested": 1,
                "threads_effective": 1,
                "parallelism_mode": "serial",
                "randomization/randomseedshift": seed,
                "limits/time": time_limit_s,
            },
            "solution": {
                "status": str(model.getStatus()),
                "objective": float(model.getSolObjVal(solution)),
                "solution_count": int(model.getNSols()),
            },
        }
    finally:
        model.freeProb()

    metadata_path = output.with_suffix(output.suffix + ".json")
    with metadata_path.open("w", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2)
    return metadata_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Solve an instance and export a checksummed SCIP .sol file."
    )
    parser.add_argument("workload", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=10000)
    parser.add_argument("--time-limit", type=float, default=None)
    arguments = parser.parse_args()
    if arguments.seed < 0:
        parser.error("--seed must be non-negative")
    if arguments.time_limit is not None and arguments.time_limit <= 0:
        parser.error("--time-limit must be positive")

    metadata_path = export_warm_start(
        arguments.workload,
        arguments.output,
        seed=arguments.seed,
        time_limit_s=arguments.time_limit,
    )
    print(f"warm_start_metadata={metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
