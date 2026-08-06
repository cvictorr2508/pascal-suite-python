import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

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

    # Trava a afinidade do SO baseada nos threads solicitados!
    if hasattr(os, "sched_setaffinity"):
        try:
            # Pega a quantidade de cores pedida (ex: 4) e gera a lista [0, 1, 2, 3]
            allowed_cores = list(range(config["threads"]))
            os.sched_setaffinity(0, allowed_cores)
        except Exception as e:
            print(f"Aviso: Falha ao fixar afinidade de CPU: {e}")


    # Coletando a afinidade real para comparação futura com os núcleos do Analyzer
    effective_cpus = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    
    metadata = {
        "adapter": "gurobi-file",
        "run_id": config.get("run_id"),
        "success": False,
        "environment": {
            "logical_cpus_available": len(effective_cpus),
            "cpu_affinity": effective_cpus
        },
        "metrics": {},
        "errors": {}
    }

    start_time = time.perf_counter()
    env = None
    model = None

    try:
        env = gp.Env(empty=True)
        env.setParam("LogFile", config["outputs"]["solver_log"])
        env.setParam("OutputFlag", 0)
        env.start()

        model = gp.read(config["workload"], env=env)

        # Aplica a direção do modelo se especificado no YAML
        sense = config.get("limits", {}).get("model_sense")
        if sense == "MINIMIZE":
            model.ModelSense = GRB.MINIMIZE
        elif sense == "MAXIMIZE":
            model.ModelSense = GRB.MAXIMIZE
        # Se não houver nada no YAML, o Gurobi usa o que vier nativo no .mps/.lp

        model.Params.Threads = config["threads"]
        model.Params.Seed = config["seed"]
        
        if "time_limit_s" in config.get("limits", {}):
            model.Params.TimeLimit = config["limits"]["time_limit_s"]

        model.optimize()

        sol_count = safe_get(model, "SolCount", 0)
        is_mip = model.IsMIP

        metadata["metrics"] = {
            "status": int(model.Status),
            "solution_count": int(sol_count),
            "gurobi_runtime_s": safe_get(model, "Runtime"),
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
