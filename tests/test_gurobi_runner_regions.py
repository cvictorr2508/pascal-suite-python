import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.runners import gurobi_runner  # noqa: E402


class _FakeEnvironment:
    def __init__(self, **_kwargs):
        pass

    def setParam(self, _name, _value):
        pass

    def start(self):
        pass

    def dispose(self):
        pass


class _FakeParameters:
    Threads = 0
    Seed = 0
    TimeLimit = float("inf")


class _FakeConstants:
    MINIMIZE = 1
    MAXIMIZE = -1


class _FakeModel:
    def __init__(self):
        self.Params = _FakeParameters()
        self.Status = 2
        self.Runtime = 1.5
        self.Work = 0.5
        self.NodeCount = 0.0
        self.SolCount = 1
        self.ObjVal = 42.0
        self.ObjBound = 41.0
        self.MIPGap = 1.0 / 42.0
        self.IsMIP = True
        self.NumVars = 12
        self.NumConstrs = 7
        self.NumBinVars = 5
        self.NumIntVars = 2
        self.ModelSense = -1
        self.Fingerprint = 12345

    def setParam(self, name, value):
        setattr(self.Params, name, value)

    def optimize(self):
        pass

    def update(self):
        self.Fingerprint = 54321

    def dispose(self):
        pass


class _FakeGurobi:
    Env = _FakeEnvironment
    GRB = _FakeConstants

    @staticmethod
    def read(_workload, env=None):
        if env is None:
            raise AssertionError("runner must reuse the configured environment")
        return _FakeModel()


class GurobiRunnerRegionTests(unittest.TestCase):
    def test_runner_emits_canonical_nested_regions(self):
        events = []

        @contextmanager
        def record_region(region_id, **_metadata):
            events.append(("START", region_id))
            try:
                yield
            finally:
                events.append(("STOP", region_id))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workload = tmp_path / "instance.lp"
            workload.write_text("placeholder", encoding="utf-8")
            base_config = tmp_path / "base_config.json"
            base_config.write_text(
                json.dumps(
                    {
                        "output_dir": str(tmp_path),
                        "workloads_list": [str(workload.resolve())],
                        "profile": {
                            "id": "default",
                            "kind": "default",
                            "objective_sense": "minimize",
                        },
                    }
                ),
                encoding="utf-8",
            )

            status = {
                "available": True,
                "backend": "proxy",
                "library_path": "/opt/pascal/lib/libmpascalops.so",
                "start_symbol": None,
                "stop_symbol": None,
                "proxy_command_fd": 7,
                "proxy_ack_fd": 8,
            }
            argv = [
                "gurobi_runner.py",
                "--base-config",
                str(base_config),
                "--workload",
                str(workload),
            ]
            with (
                patch.object(gurobi_runner, "gp", _FakeGurobi),
                patch.object(gurobi_runner, "pascal_region", record_region),
                patch.object(
                    gurobi_runner,
                    "instrumentation_status",
                    return_value=status,
                ),
                patch.object(gurobi_runner, "_current_affinity", return_value=None),
                patch.dict(
                    gurobi_runner.os.environ,
                    {"PASCAL_GLOBAL_INPUT_INDEX": "4"},
                ),
                patch.object(sys, "argv", argv),
            ):
                gurobi_runner.main()

            metadata_paths = list(tmp_path.glob("meta_*.json"))
            self.assertEqual(len(metadata_paths), 1)
            metadata = json.loads(metadata_paths[0].read_text(encoding="utf-8"))

        self.assertEqual(
            events,
            [
                ("START", 0),
                ("START", 1),
                ("STOP", 1),
                ("START", 2),
                ("STOP", 2),
                ("STOP", 0),
            ],
        )
        self.assertEqual(
            set(metadata["pascal_instrumentation"]["region_schema"]["regions"]),
            {"0", "0.1", "0.2"},
        )
        self.assertEqual(metadata["input_idx"], 4)
        self.assertEqual(metadata["local_input_idx"], 0)
        self.assertEqual(metadata["parameters"]["seed_requested"], 10004)
        self.assertIn("read_wall_clock_s", metadata["metrics"])
        self.assertIn("solve_wall_clock_s", metadata["metrics"])
        self.assertEqual(metadata["metrics"]["status_name"], "OPTIMAL")
        self.assertEqual(metadata["metrics"]["best_bound"], 41.0)
        self.assertAlmostEqual(metadata["metrics"]["mip_gap"], 1.0 / 42.0)
        self.assertEqual(metadata["metrics"]["num_binary_variables"], 5)
        self.assertEqual(metadata["objective_sense"]["source_name"], "maximize")
        self.assertEqual(metadata["objective_sense"]["effective_name"], "minimize")
        self.assertTrue(metadata["objective_sense"]["overridden"])
        self.assertEqual(metadata["objective_sense"]["fingerprint_before"], 12345)
        self.assertEqual(metadata["objective_sense"]["fingerprint_after"], 54321)


if __name__ == "__main__":
    unittest.main()

