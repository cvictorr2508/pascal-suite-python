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
                patch.dict(
                    "os.environ",
                    {
                        "PASCAL_SOURCE_COMMIT": "a" * 40,
                        "PASCAL_SOURCE_BRANCH": "feature/test",
                        "PASCAL_SOURCE_TRACKED_CLEAN": "true",
                        "PASCAL_SLURM_ALLOCATION_MODE": "shared",
                        "PASCAL_SLURM_OVERSUBSCRIBE": "YES",
                        "PASCAL_SLURM_EXCLUSIVE": "",
                    },
                ),
                patch("pascalpy.cli._distribution_version", return_value="1.0"),
            ):
                manifest = build_research_manifest(
                    config_path=configuration_path,
                    configuration=configuration,
                    profiles=profiles,
                )

        self.assertEqual(
            manifest["workloads"][0]["sha256"],
            hashlib.sha256(b"workload").hexdigest(),
        )
        self.assertEqual(
            manifest["initial_solutions"][0]["sha256"],
            hashlib.sha256(b"start").hexdigest(),
        )
        self.assertEqual(manifest["source"]["git_commit"], "a" * 40)
        self.assertEqual(manifest["source"]["git_branch"], "feature/test")
        self.assertTrue(manifest["source"]["tracked_worktree_clean"])
        self.assertEqual(
            manifest["source"]["capture_method"], "submission-environment"
        )
        self.assertEqual(
            manifest["experiment"]["profiles"][0]["kind"], "warm-start"
        )
        self.assertEqual(
            manifest["slurm"]["allocation"],
            {
                "requested_mode": "shared",
                "scheduler_oversubscribe": "YES",
                "scheduler_exclusive": None,
            },
        )

    def test_submission_policy_defaults_to_exclusive_and_supports_shared(self):
        launcher = (
            PROJECT_ROOT / "jobs" / "submit_solver_experiment.sh"
        ).read_text(encoding="utf-8")
        slurm_job = (
            PROJECT_ROOT / "jobs" / "run_solver_experiment.slurm"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'ALLOCATION_MODE="${PASCAL_SLURM_ALLOCATION_MODE:-exclusive}"',
            launcher,
        )
        self.assertIn('ALLOCATION_ARGUMENTS=(--exclusive)', launcher)
        self.assertIn('ALLOCATION_ARGUMENTS=(--oversubscribe)', launcher)
        self.assertIn("submission_error=invalid_allocation_mode", launcher)
        self.assertNotIn("#SBATCH --exclusive", slurm_job)
        self.assertIn("preflight_error=invalid_allocation_mode", slurm_job)


if __name__ == "__main__":
    unittest.main()
