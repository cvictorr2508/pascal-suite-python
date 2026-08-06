import subprocess
from pathlib import Path
from typing import Any

class LocalExecutor:
    """Executa a matriz do experimento diretamente no nó de computação atual."""
    def __init__(self, experiment: Any):
        self.experiment = experiment

    def run_all(self):
        output_dir = self.experiment.output.directory
        plan = self.experiment.generate_execution_plan()
        
        for run_idx, task in enumerate(plan, 1):
            cores = task["cores"]
            workload = Path(task["workload"])
            repetition = task["repetition"]
            
            print(f"\n---> Iniciando Rodada {run_idx}/{len(plan)}: Cores={cores}, Rep={repetition} <---")
            
            # Pede ao adaptador para montar o comando do pascalanalyzer
            cmd_list = self.experiment.adapter.build_analyzer_command(
                experiment_id=self.experiment.id,
                cores=cores,
                workload=workload,
                repetition=repetition,
                output_dir=output_dir,
                env_policy=self.experiment.environment
            )
            
            # O subprocess converte a lista em comando de terminal e executa
            print(f"Executando: {' '.join(str(x) for x in cmd_list)}")
            subprocess.run(cmd_list, check=False)
