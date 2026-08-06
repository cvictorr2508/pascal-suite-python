import shlex
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

class SlurmConfig(BaseModel):
    """
    Configuração das diretivas do SLURM para clusters como o NPAD.
    """
    job_name: str = Field(default="pascal_experiment", description="Nome do job no SLURM.")
    nodes: int = Field(default=1, description="Número de nós solicitados.")
    ntasks: int = Field(default=1, description="Número de tarefas MPI (1 para MPI single-node).")
    exclusive: bool = Field(
        default=True, 
        description="Garante que nenhum outro job rode no mesmo nó para evitar ruído."
    )
    time_limit: str = Field(default="24:00:00", description="Tempo máximo (HH:MM:SS).")
    partition: str | None = Field(default=None, description="Partição (ex: 'intel-256').")
    
    modules_to_load: list[str] = Field(
        default_factory=lambda: [
            "softwares/python/3.13.7-gnu8",
            "softwares/pascalsuite/2025-07-08"
        ],
        description="Módulos a serem carregados."
    )
    venv_path: str | None = Field(default=None, description="Caminho do venv para ativar.")
    pre_commands: list[str] = Field(default_factory=list, description="Comandos extras.")

class SlurmGenerator:
    def __init__(self, experiment: Any, config: SlurmConfig):
        self.experiment = experiment
        self.config = config

    def _render_header(self) -> str:
        """Gera o cabeçalho com as diretivas #SBATCH."""
        max_cpus = max(self.experiment.resources) if self.experiment.resources else 1
        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={self.config.job_name}",
            f"#SBATCH --nodes={self.config.nodes}",
            f"#SBATCH --ntasks-per-node={self.config.ntasks}",
            f"#SBATCH --cpus-per-task={max_cpus}",
            f"#SBATCH --time={self.config.time_limit}",
        ]
        if self.config.exclusive:
            lines.append("#SBATCH --exclusive")
        if self.config.partition:
            lines.append(f"#SBATCH --partition={self.config.partition}")
            
        lines.append(f"#SBATCH --output=logs/%x_%j.out")
        lines.append(f"#SBATCH --error=logs/%x_%j.err")
        
        # Modo Bash estrito
        lines.append("\nset -Eeuo pipefail")
        lines.append('cd "$SLURM_SUBMIT_DIR"\n')
        return "\n".join(lines)

    def _render_environment(self) -> str:
        lines = [
            "source /etc/profile",
            "source /etc/profile.d/modules.sh 2>/dev/null || true",
            "module purge"
        ]
        for mod in self.config.modules_to_load:
            lines.append(f"module load {mod}")
        if self.config.venv_path:
            lines.append(f"source {self.config.venv_path}")
        for cmd in self.config.pre_commands:
            lines.append(cmd)
        return "\n".join(lines)

    def _render_tasks(self, output_dir: Path) -> str:
        lines = [f'\nmkdir -p "{output_dir.resolve()}"', 'mkdir -p "logs"\n']
        
        plan = self.experiment.generate_execution_plan()
        for run_idx, task in enumerate(plan, 1):
            cores = task["cores"]
            workload = Path(task["workload"])
            repetition = task["repetition"]
            
            lines.append(f"echo '--- Rodada {run_idx}/{len(plan)}: Cores={cores}, Rep={repetition} ---'")
            
            # Passamos o EnvironmentPolicy da classe Experiment para o adaptador
            cmd_list = self.experiment.adapter.build_analyzer_command(
                experiment_id=self.experiment.id,
                cores=cores,
                workload=workload,
                repetition=repetition,
                output_dir=output_dir.resolve(),
                env_policy=self.experiment.environment
            )
            
            # shlex.join garante o escaping seguro de espaços no shell
            command_str = shlex.join(map(str, cmd_list))
            lines.append(command_str)
            lines.append(f"sleep {self.experiment.environment.idle_time_seconds}\n")
            
        return "\n".join(lines)

    def write_script(self, output_filename: str = "submit.slurm") -> Path:
        output_dir = self.experiment.output.directory
        script_content = "\n".join([
            self._render_header(),
            self._render_environment(),
            self._render_tasks(output_dir)
        ])
        
        out_path = Path(output_filename)
        with out_path.open("w", encoding="utf-8") as f:
            f.write(script_content)
        return out_path
