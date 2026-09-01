import json
import sys
from pathlib import Path

from pascalpy.instrumentation.proxy_builder import (
    build_region_proxy,
    resolve_pascal_ops_library,
)


class GurobiFileAdapter:
    def __init__(self, limits=None):
        self.limits = limits or {}

    def build_batch_command(
        self,
        exp_name: str,
        cores_list: list,
        workloads_list: list,
        repetitions: int,
        output_dir: Path,
        env_policy=None,
    ):
        run_id = f"exp_{exp_name}_batch"
        pascal_telemetry = output_dir / f"{run_id}_pascal.json"
        base_config_path = output_dir / "base_config.json"

        workloads_str_list = [str(w.resolve()) for w in workloads_list]

        base_config = {
            "experiment_name": exp_name,
            "limits": self.limits,
            "output_dir": str(output_dir.resolve()),
            "workloads_list": workloads_str_list,
        }
        with base_config_path.open("w", encoding="utf-8") as f:
            json.dump(base_config, f, indent=2)

        c_str = ",".join(map(str, cores_list))
        i_str = ",".join(workloads_str_list)

        runner_path = Path(__file__).parent.parent / "runners" / "gurobi_runner.py"
        proxy_path = build_region_proxy(
            output_dir,
            name=f"{run_id}_region_proxy",
        )
        pascal_library = resolve_pascal_ops_library().resolve()

        # O Analyzer deve iniciar diretamente o ELF linkado com libmpascalops.
        # Configuração estática do processo Python é herdada via ambiente; o workload
        # continua sendo injetado pelo próprio PaScal através de -i.
        base_cmd = [
            "env",
            f"PASCAL_PROXY_PYTHON_BIN={sys.executable}",
            f"PASCAL_PROXY_RUNNER={runner_path.resolve()}",
            f"PASCAL_PROXY_BASE_CONFIG={base_config_path.resolve()}",
            f"PASCAL_OPS_LIB={pascal_library}",
            "pascalanalyzer",
            "-c",
            c_str,
            "-i",
            i_str,
            "-r",
            str(repetitions),
            "-t",
            "man",
            "--outp",
            str(pascal_telemetry.resolve()),
        ]

        if env_policy:
            if getattr(env_policy, "track_energy_rapl", None):
                base_cmd.extend(["--rple", str(env_policy.track_energy_rapl)])
            if getattr(env_policy, "track_cores", False):
                base_cmd.append("--prcs")
            if getattr(env_policy, "idle_time_seconds", 0) > 0:
                base_cmd.extend(["--idtm", str(int(env_policy.idle_time_seconds))])

        base_cmd.append(str(proxy_path.resolve()))
        return base_cmd
