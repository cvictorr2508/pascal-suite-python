import sys
from pathlib import Path
import yaml

# Descobre o diretório raiz do projeto (onde este script está)
BASE_DIR = Path(__file__).resolve().parent

# Garante que o Python ache a nossa biblioteca src/pascalpy
sys.path.append(str(BASE_DIR / "src"))

from pascalpy.experiment_models import Experiment, EnvironmentPolicy, OutputPolicy, ScalingMode
from pascalpy.adapters.gurobi_adapter import GurobiFileAdapter
from pascalpy.backends.local_executor import LocalExecutor

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 rodar_yaml.py <arquivo.yaml>")
        sys.exit(1)

    # 1. Carrega o YAML
    yaml_path = Path(sys.argv[1])
    if not yaml_path.is_absolute():
        yaml_path = BASE_DIR / yaml_path

    with yaml_path.open('r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)

    # 2. Transforma o texto do YAML em objetos do nosso pacote
    exp_data = config_data["experiment"]
    env_data = config_data.get("environment", {})
    out_data = config_data.get("output", {})
    
    out_data["directory"] = BASE_DIR / out_data.get("directory", "resultados")

    # Tratamento super robusto para os caminhos das instâncias (workloads)
    workloads_paths = []
    for w in exp_data["workloads"]:
        w_path = Path(w)
        # Se o caminho no YAML não for absoluto (ex: /home/user/...), ele assume que parte da raiz do projeto
        if not w_path.is_absolute():
            w_path = BASE_DIR / w_path
            
        if not w_path.exists():
            print(f"[Erro] Instância não encontrada: {w_path}")
            sys.exit(1)
            
        workloads_paths.append(w_path)

    experimento = Experiment(
        name=exp_data["name"],
        adapter=GurobiFileAdapter(),
        scaling_mode=ScalingMode(exp_data.get("scaling_mode", "strong")),
        resources=exp_data["resources"],
        workloads=workloads_paths,
        repetitions=exp_data.get("repetitions", 1),
        environment=EnvironmentPolicy(**env_data),
        output=OutputPolicy(**out_data)
    )

    # 3. Dispara a execução no nó atual
    print(f"=== INICIANDO EXPERIMENTO: {experimento.name} ===")
    executor = LocalExecutor(experimento)
    executor.run_all()
    print("=== EXPERIMENTO CONCLUÍDO ===")

if __name__ == "__main__":
    main()