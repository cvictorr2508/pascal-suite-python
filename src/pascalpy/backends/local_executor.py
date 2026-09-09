import subprocess
from pathlib import Path
from typing import Any


class LocalExecutor:
    """Execute an experiment matrix directly on the current compute node."""

    def __init__(self, experiment: Any):
        self.experiment = experiment

    def run_all(self):
        output_dir = self.experiment.output.directory
        plan = self.experiment.generate_execution_plan()

        for run_index, task in enumerate(plan, 1):
            cores = task["cores"]
            workload = Path(task["workload"])
            repetition = task["repetition"]
            print(
                f"\n---> Starting run {run_index}/{len(plan)}: "
                f"cores={cores}, repetition={repetition} <---"
            )

            # Ask the adapter for an argument-safe PaScal Analyzer command.
            command = self.experiment.adapter.build_analyzer_command(
                experiment_id=self.experiment.id,
                cores=cores,
                workload=workload,
                repetition=repetition,
                output_dir=output_dir,
                env_policy=self.experiment.environment,
            )
            print(f"Executing: {' '.join(str(item) for item in command)}")
            subprocess.run(command, check=False)

