import json
import sys
from pathlib import Path

class GurobiFileAdapter:
    def __init__(self, limits=None):
        self.limits = limits or {}

    def build_batch_command(self, exp_name: str, cores_list: list, workloads_list: list, repetitions: int, output_dir: Path, env_policy=None):
        run_id = f"exp_{exp_name}_batch"
        pascal_telemetry = output_dir / f"{run_id}_pascal.json"
        base_config_path = output_dir / f"base_config.json"
        
        # Converte caminhos para strings absolutas
        workloads_str_list = [str(w.resolve()) for w in workloads_list]

        # Salva as configurações estáticas que o runner vai ler em todas as rodadas
        base_config = {
            "experiment_name": exp_name,
            "limits": self.limits,
            "output_dir": str(output_dir.resolve()),
            "workloads_list": workloads_str_list # Usado para o runner saber qual é o input atual
        }
        with base_config_path.open("w", encoding="utf-8") as f:
            json.dump(base_config, f, indent=2)

        # Monta as strings separadas por vírgula para o PaScal
        c_str = ",".join(map(str, cores_list))
        i_str = ",".join(workloads_str_list)

        base_cmd = [
            "pascalanalyzer",
            "-c", c_str,
            "-i", i_str,
            "-r", str(repetitions),
            #"-t", "man",  # Mantemos a instrumentação manual cirúrgica
            "--outp", str(pascal_telemetry.resolve())
        ]

        if env_policy:
            if getattr(env_policy, "track_energy_rapl", None):
                base_cmd.extend(["--rple", str(env_policy.track_energy_rapl)])
            if getattr(env_policy, "track_cores", False):
                base_cmd.append("--prcs")
            if getattr(env_policy, "idle_time_seconds", 0) > 0:
                base_cmd.extend(["--idtm", str(int(env_policy.idle_time_seconds))])

        runner_path = Path(__file__).parent.parent / "runners" / "gurobi_runner.py"
        wrapper_path = output_dir / f"{run_id}_wrapper.sh"
        
        # O $1 recebe o arquivo .lp injetado dinamicamente pelo -i do PaScal
        runner_cmd_str = (
            f"#!/bin/bash\n"
            f"exec {sys.executable} {runner_path.resolve()} --base-config {base_config_path.resolve()} --workload \"$1\"\n"
        )
        
        with wrapper_path.open("w", encoding="utf-8") as f:
            f.write(runner_cmd_str)
        wrapper_path.chmod(0o755)

        base_cmd.append(str(wrapper_path.resolve()))
        return base_cmd