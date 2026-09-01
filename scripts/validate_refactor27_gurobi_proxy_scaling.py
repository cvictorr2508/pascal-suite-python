#!/usr/bin/env python3

import json
import math
import sys
from pathlib import Path

EXPECTED_CORES = (1, 2, 4)


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


def _as_nonnegative_float(value, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} não é numérico: {value!r}") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} inválido: {result!r}")
    return result


def _timing_close(a: float, b: float) -> bool:
    # O dummy é muito curto; aceitamos ruído absoluto de 20 ms ou 25%.
    tolerance = max(0.020, 0.25 * max(a, b))
    return abs(a - b) <= tolerance


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: validate_refactor27_gurobi_proxy_scaling.py OUTPUT_DIR",
            file=sys.stderr,
        )
        return 2

    output_dir = Path(sys.argv[1])
    pascal_json = output_dir / "exp_refactor27_proxy_scaling_batch_pascal.json"
    if not pascal_json.is_file():
        return fail(f"JSON PaScal ausente: {pascal_json}")

    payload = json.loads(pascal_json.read_text(encoding="utf-8"))
    data = payload.get("data") or {}
    if len(data) != len(EXPECTED_CORES):
        return fail(
            f"esperadas {len(EXPECTED_CORES)} rodadas PaScal; encontradas {len(data)}"
        )

    config = payload.get("config") or {}
    package = str(config.get("pkg", ""))
    if not package.endswith("_region_proxy"):
        return fail(f"Analyzer não aponta para o supervisor ELF esperado: {package!r}")

    runs_by_cores = {}
    for run_key, run in data.items():
        try:
            cores = int(str(run_key).split(";", 1)[0])
        except (TypeError, ValueError):
            return fail(f"run_key PaScal sem cores interpretáveis: {run_key!r}")
        if cores in runs_by_cores:
            return fail(f"mais de uma rodada PaScal para cores={cores}")
        runs_by_cores[cores] = (run_key, run)

    if set(runs_by_cores) != set(EXPECTED_CORES):
        return fail(
            f"cores no JSON PaScal={sorted(runs_by_cores)}; esperado={list(EXPECTED_CORES)}"
        )

    metadata_files = sorted(output_dir.glob("meta_*.json"))
    if len(metadata_files) != len(EXPECTED_CORES):
        return fail(
            f"esperados {len(EXPECTED_CORES)} metadatas; encontrados {len(metadata_files)}"
        )

    metadata_by_cores = {}
    for path in metadata_files:
        metadata = json.loads(path.read_text(encoding="utf-8"))
        cores = metadata.get("cores")
        if cores in metadata_by_cores:
            return fail(f"mais de um metadata para cores={cores}")
        metadata_by_cores[cores] = (path, metadata)

    if set(metadata_by_cores) != set(EXPECTED_CORES):
        return fail(
            f"cores nos metadatas={sorted(metadata_by_cores)}; esperado={list(EXPECTED_CORES)}"
        )

    summaries = []
    for cores in EXPECTED_CORES:
        run_key, run = runs_by_cores[cores]
        if not isinstance(run, dict):
            return fail(f"rodada PaScal inválida para cores={cores}: {run!r}")

        regions = run.get("regions")
        samples = regions.get("1") if isinstance(regions, dict) else None
        if not samples:
            return fail(f"região 1 ausente para cores={cores}")
        if len(samples) != 1:
            return fail(
                f"esperada 1 amostra da região 1 para cores={cores}; encontradas {len(samples)}"
            )

        sample = samples[0]
        if not isinstance(sample, list) or len(sample) < 6:
            return fail(f"amostra da região 1 inválida para cores={cores}: {sample!r}")
        if sample[5] != "gurobi_runner.py":
            return fail(
                f"filename inesperado na região 1 para cores={cores}: {sample[5]!r}"
            )

        try:
            region_duration = _as_nonnegative_float(
                float(sample[1]) - float(sample[0]),
                f"region_duration cores={cores}",
            )
        except (TypeError, ValueError) as exc:
            return fail(str(exc))

        metadata_path, metadata = metadata_by_cores[cores]
        if "error" in metadata:
            return fail(f"runner cores={cores} registrou erro: {metadata['error']}")

        instrumentation = metadata.get("pascal_instrumentation") or {}
        if instrumentation.get("available") is not True:
            return fail(f"PaScal indisponível no metadata cores={cores}")
        if instrumentation.get("backend") != "proxy":
            return fail(
                f"backend cores={cores}: esperado='proxy', obtido={instrumentation.get('backend')!r}"
            )
        if instrumentation.get("region_id") != 1:
            return fail(
                f"region_id cores={cores}: esperado=1, obtido={instrumentation.get('region_id')!r}"
            )

        parameters = metadata.get("parameters") or {}
        requested = parameters.get("threads_requested")
        effective = parameters.get("threads_effective")
        if requested != cores or effective != cores:
            return fail(
                f"threads cores={cores}: requested={requested}, effective={effective}"
            )

        affinity = metadata.get("cpu_affinity")
        if not isinstance(affinity, list) or len(affinity) != cores:
            return fail(
                f"afinidade cores={cores}: esperado {cores} CPUs, obtido={affinity!r}"
            )

        metrics = metadata.get("metrics") or {}
        try:
            gurobi_runtime = _as_nonnegative_float(
                metrics.get("gurobi_runtime_s"),
                f"gurobi_runtime_s cores={cores}",
            )
            solve_wall = _as_nonnegative_float(
                metrics.get("solve_wall_clock_s"),
                f"solve_wall_clock_s cores={cores}",
            )
        except ValueError as exc:
            return fail(str(exc))

        if not _timing_close(region_duration, solve_wall):
            return fail(
                f"região PaScal diverge do solve wall para cores={cores}: "
                f"region={region_duration:.6f}s wall={solve_wall:.6f}s"
            )
        if not _timing_close(region_duration, gurobi_runtime):
            return fail(
                f"região PaScal diverge do Gurobi Runtime para cores={cores}: "
                f"region={region_duration:.6f}s gurobi={gurobi_runtime:.6f}s"
            )

        summaries.append(
            {
                "cores": cores,
                "run_key": run_key,
                "metadata_file": str(metadata_path),
                "backend": instrumentation.get("backend"),
                "threads_requested": requested,
                "threads_effective": effective,
                "cpu_affinity": affinity,
                "region_1_duration_s": region_duration,
                "gurobi_runtime_s": gurobi_runtime,
                "solve_wall_clock_s": solve_wall,
                "region_minus_gurobi_s": region_duration - gurobi_runtime,
                "region_minus_wall_s": region_duration - solve_wall,
            }
        )

    print(
        json.dumps(
            {
                "analyzer_pkg": package,
                "expected_cores": list(EXPECTED_CORES),
                "runs": summaries,
                "proxy_scaling_valid": True,
                "speedup_asserted": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
