import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

class GurobiFileAdapter:
    """
    Adaptador padrão para problemas científicos lidos diretamente de arquivos (ex: .mps, .lp).
    Implementa a injeção determinística de parâmetros e gera a configuração imutável do runner.
    """
    def __init__(self, limits: Optional[Dict[str, Any]] = None):
        """
        :param limits: Dicionário com limites do solver, ex: {"time_limit_s": 3600}
        """
        self.limits = limits or {}

    def build_analyzer_command(
        self, 
        experiment_id: str,
        cores: int, 
        workload: Path, 
        repetition: int, 
        output_dir: Path,
        env_policy: Any = None
    ) -> List[str]:
        """
        Gera a configuração isolada da rodada e constrói o comando da CLI.
        """
        run_id = f"exp_{experiment_id}-w_{workload.stem}-c_{cores}-r_{repetition}"
        
        pascal_telemetry = output_dir / f"{run_id}_pascal.json"
        gurobi_metadata = output_dir / f"{run_id}_app_meta.json"
        gurobi_log = output_dir / f"{run_id}_solver.log"
        run_config_path = output_dir / f"{run_id}_config.json"
        
        base_seed = 10000
        paired_seed = base_seed + repetition + (hash(workload.name) % 1000)

        # Usamos .resolve() para evitar qualquer problema de caminhos relativos no subprocesso
        run_config = {
            "schema_version": "1.0",
            "run_id": run_id,
            "adapter": "gurobi-file",
            "workload": str(workload.resolve()),
            "threads": cores,
            "seed": paired_seed,
            "limits": self.limits,
            "outputs": {
                "metadata": str(gurobi_metadata.resolve()),
                "solver_log": str(gurobi_log.resolve())
            }
        }

        with run_config_path.open("w", encoding="utf-8") as f:
            json.dump(run_config, f, indent=2)

        base_cmd = [
            "pascalanalyzer",
            "-c", str(cores),
            "-r", str(repetition),
            "--outp", str(pascal_telemetry.resolve())
        ]

        if env_policy:
            if getattr(env_policy, "track_energy_rapl", None):
                base_cmd.extend(["--rple", str(env_policy.track_energy_rapl)])
            if getattr(env_policy, "track_cores", False):
                base_cmd.append("--prcs")
            if getattr(env_policy, "performance_events", None):
                base_cmd.extend(["--fgpe", ",".join(env_policy.performance_events)])
            if getattr(env_policy, "idle_time_seconds", 0) > 0:
                base_cmd.extend(["--idtm", str(int(env_policy.idle_time_seconds))])

        runner_path = Path(__file__).parent.parent / "runners" / "gurobi_runner.py"
        
        # O PaScal Analyzer rejeita strings complexas. 
        # Criamos um shell script wrapper dinâmico para encapsular o Python.
        wrapper_path = output_dir / f"{run_id}_wrapper.sh"
        
        # Usamos sys.executable para garantir que o wrapper use o Python do ambiente virtual atual
        runner_cmd_str = f"#!/bin/bash\n{sys.executable} {runner_path.resolve()} --run-config {run_config_path.resolve()}\n"
        
        with wrapper_path.open("w", encoding="utf-8") as f:
            f.write(runner_cmd_str)
        wrapper_path.chmod(0o755)

        base_cmd.append(str(wrapper_path.resolve()))

        return base_cmd
    