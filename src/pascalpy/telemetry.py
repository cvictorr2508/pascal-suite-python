import json
import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger("pascalpy.telemetry")

class PascalResult:
    """
    Representa o resultado consolidado de um experimento, 
    unindo dados do PaScal e do Solver.
    """
    def __init__(self, experiment_id: str, runs: list[dict]):
        self.experiment_id = experiment_id
        self.runs = runs

    def to_dataframe(self):
        """Achatamento dos dados para o formato tabular do Pandas."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("Pandas é necessário para exportar os resultados. Instale com 'pip install pandas'.")

        flat_data = []
        for run in self.runs:
            row = {
                "experiment_id": self.experiment_id,
                "run_id": run["run_id"],
                "cores": run["cores_pascal"],
                "repetition": run["repetition"],
            }

            # 1. Métricas do PaScal
            for k, v in run["pascal_metrics"].items():
                row[f"pascal_{k}"] = v
                
            if "start_time" in run["pascal_metrics"] and "stop_time" in run["pascal_metrics"]:
                row["pascal_wall_clock_s"] = run["pascal_metrics"]["stop_time"] - run["pascal_metrics"]["start_time"]

            # 2. Métricas do Gurobi
            app_meta = run["app_metadata"]
            row["app_success"] = app_meta.get("success", False)
            
            if "metrics" in app_meta:
                for k, v in app_meta["metrics"].items():
                    row[f"gurobi_{k}"] = v
                    
            if "runner_wall_clock_s" in app_meta:
                row["gurobi_runner_wall_clock_s"] = app_meta["runner_wall_clock_s"]

            flat_data.append(row)

        return pd.DataFrame(flat_data)


class TelemetryReader:
    """Motor de leitura de todos os JSONs gerados em um experimento."""
    def __init__(self, output_dir: Union[str, Path]):
        self.output_dir = Path(output_dir)

    def _safe_load_json(self, file_path: Path) -> Union[dict, None]:
        if not file_path.exists():
            return None
        with file_path.open('r', encoding='utf-8') as f:
            return json.load(f)

    def read_experiment(self, experiment_id: str) -> Union[PascalResult, None]:
        runs = []
        
        # --- LÓGICA DE BUSCA INTELIGENTE ---
        # Se o usuário passar "*" ou um nome de arquivo ".json" por engano
        if experiment_id == "*" or str(experiment_id).endswith(".json"):
            if str(experiment_id).endswith(".json"):
                logger.warning(f"Aviso: Você passou '{experiment_id}' como ID. Buscando todos os *_pascal.json da pasta.")
            pattern = "*_pascal.json"
        else:
            # Padrão oficial do pipeline avançado
            pattern = f"exp_{experiment_id}-*_pascal.json"

        arquivos_encontrados = list(self.output_dir.glob(pattern))

        # Fallback: Se não achar com o sufixo _pascal.json, pega qualquer pascal*.json
        if not arquivos_encontrados:
            arquivos_encontrados = list(self.output_dir.glob("*pascal*.json"))

        for pascal_file in arquivos_encontrados:
            pascal_data = self._safe_load_json(pascal_file)

            if not pascal_data or "data" not in pascal_data:
                logger.warning(f"Ignorando arquivo inválido ou incompleto: {pascal_file.name}")
                continue

            # O PaScal salva as chaves na ordem, ex: ["cores", "repetitions"]
            data_keys = pascal_data.get("config", {}).get("data_descriptor", {}).get("keys", ["cores", "repetitions"])
            
            for key_str, metrics in pascal_data["data"].items():
                key_values = key_str.split(';')
                run_identifiers = dict(zip(data_keys, key_values))
                cores = run_identifiers.get("cores", "unknown")
                rep = run_identifiers.get("repetitions", "unknown")

                # Reconstruímos o nome do app_meta ajustando qualquer terminação .json
                if "_pascal.json" in pascal_file.name:
                    app_meta_file = pascal_file.with_name(pascal_file.name.replace("_pascal.json", "_app_meta.json"))
                else:
                    app_meta_file = pascal_file.with_name(pascal_file.name.replace(".json", "_app_meta.json"))
                
                app_data = self._safe_load_json(app_meta_file)

                if not app_data:
                    logger.warning(f"Metadados do Gurobi não encontrados para {app_meta_file.name}.")

                # Limpa o run_id para não ficar com sujeira no CSV
                clean_run_id = pascal_file.name.replace("_pascal.json", "").replace(".json", "")

                runs.append({
                    "run_id": clean_run_id,
                    "cores_pascal": int(cores) if str(cores).isdigit() else cores,
                    "repetition": int(rep) if str(rep).isdigit() else rep,
                    "pascal_metrics": metrics,
                    "app_metadata": app_data or {}
                })

        if not runs:
            logger.error(f"Nenhum arquivo de telemetria encontrado em '{self.output_dir}'.")
            return None

        # Ordena a lista pela quantidade de cores para a tabela ficar bonita
        runs.sort(key=lambda x: (
            x["cores_pascal"] if isinstance(x["cores_pascal"], int) else 999, 
            x["repetition"] if isinstance(x["repetition"], int) else 999
        ))

        # Se o ID foi um curinga, usa o nome da pasta como ID
        final_id = self.output_dir.name if experiment_id in ["*", None] else experiment_id
        return PascalResult(experiment_id=final_id, runs=runs)