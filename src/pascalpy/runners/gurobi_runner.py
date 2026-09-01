import argparse
import json
import os
import sys
import time
from pathlib import Path

# O runner e executado como arquivo pelo supervisor nativo gerado pelo adapter.
# Adicionamos src/ ao sys.path para importar o pacote local sem exigir instalacao editavel.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from pascalpy.instrumentation.pascalops import (  # noqa: E402
    instrumentation_status,
    pascal_region,
)

try:
    import gurobipy as gp
except ImportError:
    gp = None


GUROBI_OPTIMIZE_REGION = 1


def safe_get(model, attr_name, default=None):
    try:
        return getattr(model, attr_name)
    except Exception:
        return default


def _current_affinity():
    if not hasattr(os, "sched_getaffinity"):
        return None
    try:
        return sorted(os.sched_getaffinity(0))
    except OSError:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-config", required=True)
    parser.add_argument("--workload", required=True)
    args = parser.parse_args()

    if gp is None:
        raise RuntimeError("gurobipy nao esta disponivel no ambiente do runner")

    with open(args.base_config, "r", encoding="utf-8") as f:
        base_config = json.load(f)

    cores = int(os.environ.get("OMP_NUM_THREADS", "1"))
    workload_str = str(Path(args.workload).resolve())

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
        if cores > len(affinity_before):
            raise RuntimeError(
                f"Configuracao invalida: cores={cores}, mas a afinidade atual permite "
                f"apenas {len(affinity_before)} CPUs: {affinity_before}"
            )
        os.sched_setaffinity(0, set(affinity_before[:cores]))

    affinity_effective = _current_affinity()
    pascal_status = instrumentation_status()

    metadata = {
        "workload": workload_str,
        "cores": cores,
        "input_idx": input_idx,
        "start_timestamp": start_timestamp,
        "cpu_affinity": affinity_effective,
        "pascal_instrumentation": {
            "requested": True,
            "available": pascal_status["available"],
            "backend": pascal_status.get("backend"),
            "library_path": pascal_status["library_path"],
            "start_symbol": pascal_status["start_symbol"],
            "stop_symbol": pascal_status["stop_symbol"],
            "proxy_command_fd": pascal_status.get("proxy_command_fd"),
            "proxy_ack_fd": pascal_status.get("proxy_ack_fd"),
            "region_id": GUROBI_OPTIMIZE_REGION,
        },
        "parameters": {
            "threads_requested": cores,
            "threads_effective": None,
        },
        "metrics": {},
    }

    env = None
    model = None
    solve_wall_s = 0.0
    try:
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 0)
        env.start()
        model = gp.read(args.workload, env=env)

        model.Params.Threads = cores
        model.Params.Seed = 10000 + input_idx
        metadata["parameters"]["threads_effective"] = int(model.Params.Threads)

        if metadata["parameters"]["threads_effective"] != cores:
            raise RuntimeError(
                "Gurobi Threads divergiu da configuracao PaScal: "
                f"requested={cores}, effective={model.Params.Threads}"
            )

        # A região PaScal 1 cobre somente model.optimize(). O supervisor nativo
        # executa os marcadores, mas recebe filename/linha do ponto Python real.
        optimize_line = sys._getframe().f_lineno + 2
        t_solve_start = time.perf_counter()
        with pascal_region(
            GUROBI_OPTIMIZE_REGION,
            filename=Path(__file__).name,
            start_line=optimize_line,
            stop_line=optimize_line,
        ):
            model.optimize()
        solve_wall_s = time.perf_counter() - t_solve_start

        metadata["metrics"] = {
            "status": int(model.Status),
            "gurobi_runtime_s": safe_get(model, "Runtime"),
            "solve_wall_clock_s": solve_wall_s,
            "work": safe_get(model, "Work"),
            "node_count": safe_get(model, "NodeCount"),
            "objective": (
                float(model.ObjVal) if safe_get(model, "SolCount", 0) > 0 else None
            ),
        }
    except Exception as exc:
        metadata["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        raise
    finally:
        if model is not None:
            model.dispose()
        if env is not None:
            env.dispose()

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)


if __name__ == "__main__":
    main()
