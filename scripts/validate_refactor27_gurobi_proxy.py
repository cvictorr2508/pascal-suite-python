#!/usr/bin/env python3

import json
import sys
from pathlib import Path


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: validate_refactor27_gurobi_proxy.py OUTPUT_DIR",
            file=sys.stderr,
        )
        return 2

    output_dir = Path(sys.argv[1])
    pascal_json = output_dir / "exp_refactor27_proxy_smoke_batch_pascal.json"
    if not pascal_json.is_file():
        return fail(f"JSON PaScal ausente: {pascal_json}")

    payload = json.loads(pascal_json.read_text(encoding="utf-8"))
    data = payload.get("data") or {}
    if len(data) != 1:
        return fail(f"esperada 1 rodada PaScal; encontradas {len(data)}")

    run_key, run = next(iter(data.items()))
    regions = run.get("regions") if isinstance(run, dict) else None
    samples = regions.get("1") if isinstance(regions, dict) else None
    if not samples:
        return fail("região 1 ausente no JSON nativo do Analyzer")

    first = samples[0]
    if not isinstance(first, list) or len(first) < 6:
        return fail(f"amostra da região 1 inválida: {first!r}")
    duration = float(first[1]) - float(first[0])
    if duration < 0:
        return fail(f"duração negativa da região 1: {duration}")

    metadata_files = sorted(output_dir.glob("meta_*.json"))
    if len(metadata_files) != 1:
        return fail(
            f"esperado exatamente 1 metadata do runner; encontrados {len(metadata_files)}"
        )

    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    if "error" in metadata:
        return fail(f"runner registrou erro: {metadata['error']}")

    instrumentation = metadata.get("pascal_instrumentation") or {}
    if instrumentation.get("available") is not True:
        return fail("metadata não marca instrumentação PaScal como disponível")
    if instrumentation.get("backend") != "proxy":
        return fail(
            f"backend esperado='proxy'; obtido={instrumentation.get('backend')!r}"
        )
    if instrumentation.get("region_id") != 1:
        return fail(f"region_id esperado=1; obtido={instrumentation.get('region_id')!r}")

    parameters = metadata.get("parameters") or {}
    requested = parameters.get("threads_requested")
    effective = parameters.get("threads_effective")
    if requested != 1 or effective != 1:
        return fail(
            f"invariante de threads violada: requested={requested}, effective={effective}"
        )

    metrics = metadata.get("metrics") or {}
    if metrics.get("gurobi_runtime_s") is None:
        return fail("gurobi_runtime_s ausente")
    if metrics.get("solve_wall_clock_s") is None:
        return fail("solve_wall_clock_s ausente")

    config = payload.get("config") or {}
    package = str(config.get("pkg", ""))
    if not package.endswith("_region_proxy"):
        return fail(f"Analyzer não aponta para o supervisor ELF esperado: {package!r}")

    summary = {
        "run_key": run_key,
        "region_1_duration_s": duration,
        "region_1_sample": first,
        "metadata_file": str(metadata_files[0]),
        "backend": instrumentation.get("backend"),
        "threads_requested": requested,
        "threads_effective": effective,
        "gurobi_runtime_s": metrics.get("gurobi_runtime_s"),
        "solve_wall_clock_s": metrics.get("solve_wall_clock_s"),
        "analyzer_pkg": package,
        "proxy_smoke_valid": True,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
