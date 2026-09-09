import shlex
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SlurmConfig(BaseModel):
    """Slurm directives for HPC environments such as NPAD."""

    job_name: str = Field(default="pascal_experiment", description="Slurm job name.")
    nodes: int = Field(default=1, description="Number of requested nodes.")
    ntasks: int = Field(default=1, description="Number of MPI tasks.")
    exclusive: bool = Field(
        default=True,
        description="Reserve the node exclusively to reduce measurement noise.",
    )
    time_limit: str = Field(default="24:00:00", description="Maximum HH:MM:SS time.")
    partition: str | None = Field(default=None, description="Slurm partition name.")
    modules_to_load: list[str] = Field(
        default_factory=lambda: [
            "softwares/python/3.13.7-gnu8",
            "softwares/pascalsuite/2025-07-08",
        ],
        description="Environment modules loaded before execution.",
    )
    venv_path: str | None = Field(
        default=None,
        description="Optional virtual-environment activation path.",
    )
    pre_commands: list[str] = Field(
        default_factory=list,
        description="Additional shell commands executed before the experiment.",
    )


class SlurmGenerator:
    def __init__(self, experiment: Any, config: SlurmConfig):
        self.experiment = experiment
        self.config = config

    def _render_header(self) -> str:
        """Render the Slurm header and its `#SBATCH` directives."""
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

        lines.append("#SBATCH --output=logs/%x_%j.out")
        lines.append("#SBATCH --error=logs/%x_%j.err")
        lines.append("\nset -Eeuo pipefail")
        lines.append('cd "$SLURM_SUBMIT_DIR"\n')
        return "\n".join(lines)

    def _render_environment(self) -> str:
        lines = [
            "source /etc/profile",
            "source /etc/profile.d/modules.sh 2>/dev/null || true",
            "module purge",
        ]
        for module in self.config.modules_to_load:
            lines.append(f"module load {module}")
        if self.config.venv_path:
            lines.append(f"source {self.config.venv_path}")
        lines.extend(self.config.pre_commands)
        return "\n".join(lines)

    def _render_tasks(self, output_dir: Path) -> str:
        lines = [f'\nmkdir -p "{output_dir.resolve()}"', 'mkdir -p "logs"\n']
        plan = self.experiment.generate_execution_plan()
        for run_index, task in enumerate(plan, 1):
            cores = task["cores"]
            workload = Path(task["workload"])
            repetition = task["repetition"]
            lines.append(
                f"echo '--- Run {run_index}/{len(plan)}: "
                f"cores={cores}, repetition={repetition} ---'"
            )
            command = self.experiment.adapter.build_analyzer_command(
                experiment_id=self.experiment.id,
                cores=cores,
                workload=workload,
                repetition=repetition,
                output_dir=output_dir.resolve(),
                env_policy=self.experiment.environment,
            )
            lines.append(shlex.join(map(str, command)))
            lines.append(f"sleep {self.experiment.environment.idle_time_seconds}\n")
        return "\n".join(lines)

    def write_script(self, output_filename: str = "submit.slurm") -> Path:
        output_dir = self.experiment.output.directory
        script_content = "\n".join(
            [
                self._render_header(),
                self._render_environment(),
                self._render_tasks(output_dir),
            ]
        )
        output_path = Path(output_filename)
        output_path.write_text(script_content, encoding="utf-8", newline="\n")
        return output_path
