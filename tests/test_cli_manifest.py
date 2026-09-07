import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.cli import build_research_manifest  # noqa: E402
from pascalpy.experiment_profiles import SolverProfile  # noqa: E402


class ResearchManifestTests(unittest.TestCase):
    def test_manifest_checksums_workload_and_initial_solution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            configuration_path = root / "experiment.yaml"
            configuration_path.write_text("experiment: {}\n", encoding="utf-8")
            workload = root / "instance.lp.gz"
            workload.write_bytes(b"workload")
            solution = root / "instance.mst"
            solution.write_bytes(b"start")
            configuration = {
                "experiment": {
                    "name": "manifest-test",
                    "solver": "gurobi",
                    "resources": [1],
                    "repetitions": 1,
                    "workloads": [str(workload)],
                }
            }
            profiles = [
                SolverProfile.model_validate(
                    {
                        "id": "warm-start",
                        "kind": "warm-start",
                        "initial_solution": {
                            "files": {workload.name: str(solution)},
                            "required": True,
                        },
                    }
                )
            ]

            with (
                patch("pascalpy.cli._git_value", return_value="abc123"),
                patch("pascalpy.cli._distribution_version", return_value="1.0"),
            ):
                manifest = build_research_manifest(
                    config_path=configuration_path,
                    configuration=configuration,
                    profiles=profiles,
                    project_root=root,
                )

        self.assertEqual(
            manifest["workloads"][0]["sha256"],
            hashlib.sha256(b"workload").hexdigest(),
        )
        self.assertEqual(
            manifest["initial_solutions"][0]["sha256"],
            hashlib.sha256(b"start").hexdigest(),
        )
        self.assertEqual(manifest["source"]["git_commit"], "abc123")
        self.assertEqual(
            manifest["experiment"]["profiles"][0]["kind"], "warm-start"
        )


if __name__ == "__main__":
    unittest.main()

