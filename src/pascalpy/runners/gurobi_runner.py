import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# [NOVO] 1. Importação segura do binding PaScal
sys.path.append(str(Path(__file__).resolve().parents[2]))
from pascalpy.instrumentation.pascalops import pascal_region

try:
    import gurobipy as gp
    from gurobipy import GRB
except ImportError:
    gp = None

def safe_get(model: 'gp.Model', attr_name: str, default: Any = None) -> Any:
    """Extrai atributos do Gurobi de forma segura, ignorando erros de estado."""
    try:
        return getattr(model, attr_name)
    except gp.GurobiError:
        return default

def write_atomic_json(payload: dict, path: Path) -> None:
    """Garante que metadados nunca fiquem corrompidos."""
    temp_path = path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    temp_path.replace(path)

def main():
    if gp is None:
        print("Erro: gurobipy não encontrado no ambiente.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="PaScalPy Gurobi Isolated Runner")
    parser.add_argument("--run-config", required=True, help="JSON de configuração da rodada")
    args = parser.parse_args()

    config_path = Path(args.run_config)
    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    # [NOVO] 2. Trava a afinidade do SO baseada no SLURM e nos threads solicitados!
    cpu_affinity_count = 0
    if hasattr(os, "sched_setaffinity") and hasattr(os, "sched_getaffinity"):
        try:
            slurm_cpus = sorted(os.sched_getaffinity(0))
            allowed_cores = slurm_cpus[:config["threads"]]
            os.sched_setaffinity(0, set(allowed_cores))
            cpu_affinity_count = len(allowed_cores)
        except Exception as e:
            print(f"Aviso: Falha ao fixar afinidade de CPU: {e}")

    # Coletando a afinidade real
    effective_cpus = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    
    metadata = {
        "adapter": "gurobi-file",
        "run_id": config.get("run_id"),
        "success": False,
        "environment": {
            "logical_cpus_available": len(effective_cpus),
            "cpu_affinity": effective_cpus,
            "omp_num_threads": os.environ.get("OMP_NUM_THREADS") # [NOVO]
        },
        "metrics": {},
        "errors": {}
    }

    start_time = time.perf_counter()
    env = None
    model = None
    solve_wall_s = 0.0 # [NOVO] Inicializando variável de tempo

    try:
        env = gp.Env(empty=True)
        env.setParam("LogFile", config["outputs"]["solver_log"])
        env.setParam("OutputFlag", 0)
        env.start()

        model = gp.read(config["workload"], env=env)

        sense = config.get("limits", {}).get("model_sense")
        if sense == "MINIMIZE":
            model.ModelSense = GRB.MINIMIZE
        elif sense == "MAXIMIZE":
            model.ModelSense = GRB.MAXIMIZE

        model.Params.Threads = config["threads"]
        model.Params.Seed = config["seed"]
        
        if "time_limit_s" in config.get("limits", {}):
            model.Params.TimeLimit = config["limits"]["time_limit_s"]

        # [NOVO] 3. A Janela Cirúrgica de Medição
        t_solve_start = time.perf_counter()
        
        with pascal_region(1):
            model.optimize()
            
        solve_wall_s = time.perf_counter() - t_solve_start
        # ----------------------------------------

        sol_count = safe_get(model, "SolCount", 0)
        is_mip = model.IsMIP

        # [NOVO] 4. Atualizando os Invariantes na Telemetria
        metadata["environment"]["gurobi_threads_effective"] = safe_get(model, "Threads")
        
        metadata["metrics"] = {
            "status": int(model.Status),
            "solution_count": int(sol_count),
            "gurobi_runtime_s": safe_get(model, "Runtime"),
            "solve_wall_clock_s": solve_wall_s,           # [NOVO]
            "pascal_cores_requested": config["threads"],  # [NOVO]
            "cpu_affinity_count": cpu_affinity_count,     # [NOVO]
            "work_units": safe_get(model, "Work"),
            "node_count": safe_get(model, "NodeCount") if is_mip else None,
            "simplex_iterations": safe_get(model, "IterCount"),
            "barrier_iterations": safe_get(model, "BarIterCount"),
            "objective": float(model.ObjVal) if sol_count > 0 else None,
            "mip_gap": float(model.MIPGap) if (is_mip and sol_count > 0) else None
        }
        metadata["success"] = True

    except Exception as exc:
        metadata["errors"] = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
        }
    finally:
        if model:
            model.dispose()
        if env:
            env.dispose()
            
        metadata["runner_wall_clock_s"] = time.perf_counter() - start_time
        write_atomic_json(metadata, Path(config["outputs"]["metadata"]))

if __name__ == "__main__":
    main()