import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from pascalpy.instrumentation.pascalops import pascal_region

try:
    import gurobipy as gp
    from gurobipy import GRB
except ImportError:
    gp = None

def safe_get(model, attr_name, default=None):
    try: return getattr(model, attr_name)
    except: return default

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-config", required=True)
    parser.add_argument("--workload", required=True)
    args = parser.parse_args()

    with open(args.base_config, "r") as f:
        base_config = json.load(f)

    # 1. Descobre a configuração dinâmica injetada pelo PaScal
    cores = int(os.environ.get("OMP_NUM_THREADS", "1"))
    workload_str = str(Path(args.workload).resolve())
    
    try:
        input_idx = base_config["workloads_list"].index(workload_str)
    except ValueError:
        input_idx = 0

    # 2. Gera um nome de arquivo seguro e único baseado no timestamp para não sobrescrever
    start_timestamp = time.time()
    meta_path = Path(base_config["output_dir"]) / f"meta_c{cores}_i{input_idx}_{int(start_timestamp*1000)}.json"

    # Afinidade segura
    if hasattr(os, "sched_setaffinity") and hasattr(os, "sched_getaffinity"):
        try:
            slurm_cpus = sorted(os.sched_getaffinity(0))
            os.sched_setaffinity(0, set(slurm_cpus[:cores]))
        except: pass

    metadata = {
        "workload": workload_str,
        "cores": cores,
        "input_idx": input_idx,
        "start_timestamp": start_timestamp,
        "metrics": {}
    }

    env = None; model = None; solve_wall_s = 0.0
    try:
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 0)
        env.start()
        model = gp.read(args.workload, env=env)

        model.Params.Threads = cores
        model.Params.Seed = 10000 + input_idx  # Semente determinística baseada na instância
        
        # 3. Medição Cirúrgica
        t_solve_start = time.perf_counter()
        with pascal_region(1):
            model.optimize()
        solve_wall_s = time.perf_counter() - t_solve_start

        metadata["metrics"] = {
            "status": int(model.Status),
            "gurobi_runtime_s": safe_get(model, "Runtime"),
            "solve_wall_clock_s": solve_wall_s,
            "objective": float(model.ObjVal) if safe_get(model, "SolCount", 0) > 0 else None,
        }
    except Exception as e:
        metadata["error"] = str(e)
    finally:
        if model: model.dispose()
        if env: env.dispose()
        
        # Salva as métricas locais para o consolidador CSV
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

if __name__ == "__main__":
    main()