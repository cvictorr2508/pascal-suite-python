import yaml
import subprocess
import sys
from pathlib import Path
from pascalpy.adapters.gurobi_adapter import GurobiFileAdapter

def main():
    yaml_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("meu_experimento.yaml")
    
    with yaml_path.open("r") as f:
        config = yaml.safe_load(f)

    exp_cfg = config["experiment"]
    out_cfg = config["output"]
    
    output_dir = Path(out_cfg["directory"])
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepara as listas
    cores_list = exp_cfg["resources"]
    workloads_list = [Path(w) for w in exp_cfg["workloads"]]
    repetitions = exp_cfg["repetitions"]

    # Cria a política de ambiente
    class EnvPolicy:
        track_energy_rapl = config["environment"].get("track_energy_rapl")
        track_cores = config["environment"].get("track_cores", False)
        idle_time_seconds = config["environment"].get("idle_time_seconds", 0)

    adapter = GurobiFileAdapter()
    
    print("\n=== GERANDO LOTE DO PASCAL ANALYZER ===")
    cmd = adapter.build_batch_command(
        exp_name=exp_cfg["name"],
        cores_list=cores_list,
        workloads_list=workloads_list,
        repetitions=repetitions,
        output_dir=output_dir,
        env_policy=EnvPolicy()
    )

    print(f"Executando: {' '.join(cmd)}")
    
    # Entrega o controle para o PaScal Analyzer fazer a mágica dele!
    subprocess.run(cmd, check=True)
    
    print("=== LOTE CONCLUÍDO ===")

if __name__ == "__main__":
    main()