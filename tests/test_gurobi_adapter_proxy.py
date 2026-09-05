import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.adapters.gurobi_adapter import GurobiFileAdapter


class _EnvPolicy:
    track_energy_rapl = "sysfs"
    track_cores = False
    idle_time_seconds = 0


class GurobiAdapterProxyTests(unittest.TestCase):
    def test_analyzer_targets_native_proxy_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "out"
            output_dir.mkdir()
            workload = root / "dummy.mps"
            workload.write_text("NAME DUMMY\nENDATA\n", encoding="utf-8")
            proxy = output_dir / "exp_test_batch_region_proxy"

            with (
                patch(
                    "pascalpy.adapters.gurobi_adapter.build_region_proxy",
                    return_value=proxy,
                ),
                patch(
                    "pascalpy.adapters.gurobi_adapter.resolve_pascal_ops_library",
                    return_value=Path("/opt/pascal/lib/libmpascalops.so"),
                ),
            ):
                command = GurobiFileAdapter().build_batch_command(
                    exp_name="test",
                    cores_list=[1, 2],
                    workloads_list=[workload],
                    repetitions=1,
                    output_dir=output_dir,
                    env_policy=_EnvPolicy(),
                )

        self.assertEqual(command[0], "env")
        self.assertIn("pascalanalyzer", command)
        self.assertIn("-t", command)
        self.assertIn("man", command)
        self.assertIn("--rple", command)
        self.assertIn("--rpls", command)
        self.assertEqual(command[command.index("--rple") + 1], "sysfs")
        self.assertEqual(command[command.index("--rpls") + 1], "sysfs")
        self.assertEqual(command[-1], str(proxy.resolve()))
        self.assertTrue(
            any(item.startswith("PASCAL_PROXY_PYTHON_BIN=") for item in command)
        )
        self.assertTrue(
            any(item.startswith("PASCAL_PROXY_RUNNER=") for item in command)
        )
        self.assertTrue(
            any(item.startswith("PASCAL_PROXY_BASE_CONFIG=") for item in command)
        )
        self.assertFalse(any(item.endswith("_wrapper.sh") for item in command))

    def test_nested_smoke_uses_available_partition_and_compressed_workload(self):
        slurm = (
            PROJECT_ROOT / "refactor28_gurobi_nested_smoke.slurm"
        ).read_text(encoding="utf-8")
        configuration = (
            PROJECT_ROOT / "refactor28_gurobi_nested_smoke.yaml"
        ).read_text(encoding="utf-8")

        self.assertIn("#SBATCH --partition=intel-128", slurm)
        self.assertIn("preflight_error=", slurm)
        self.assertIn("command -v gzip", slurm)
        self.assertIn("CFL_hard_instance_20.lp.gz", slurm)
        self.assertIn("CFL_hard_instance_20.lp.gz", configuration)
        self.assertNotIn("CFL_hard_instance_20.lp\n", configuration)

        candidate_probe = (
            PROJECT_ROOT / "refactor28_gurobi_candidate_probe.slurm"
        ).read_text(encoding="utf-8")
        profiler_probe = (
            PROJECT_ROOT / "refactor28_profiler_import_probe.slurm"
        ).read_text(encoding="utf-8")

        self.assertIn("CFL_hard_instance_${candidate_id}.lp.gz", candidate_probe)
        self.assertIn("#SBATCH --partition=intel-128", profiler_probe)


if __name__ == "__main__":
    unittest.main()
