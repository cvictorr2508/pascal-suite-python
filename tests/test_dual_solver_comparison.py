import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "compare_solver_profile_matrices.py"
SPEC = importlib.util.spec_from_file_location("dual_solver_comparison", SCRIPT_PATH)
COMPARISON = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(COMPARISON)


def _run(profile: str, solver: str, duration: float, energy: float) -> dict:
    return {
        "run": "1;0;1",
        "configuration": {
            "cores": 1,
            "input_index": 0,
            "repetition": 1,
            "workload": "/data/CFL_hard_instance_20.lp.gz",
        },
        "regions": {
            "0.2": {
                "duration_s": duration,
                "energy_j": energy,
            }
        },
    }


def _write_campaign(root: Path, solver: str, *, workload_sha: str) -> None:
    manifest = {
        "source": {
            "git_commit": ("a" if solver == "gurobi" else "b") * 40,
            "git_branch": f"feature/{solver}",
            "tracked_worktree_clean": True,
        },
        "runtime": {"python_version": "3.13.15"},
        "experiment": {
            "solver": solver,
            "resources": [1],
            "repetitions": 1,
        },
        "workloads": [
            {
                "path": "/data/CFL_hard_instance_20.lp.gz",
                "size_bytes": 123,
                "sha256": workload_sha,
            }
        ],
        "slurm": {
            "SLURM_JOB_PARTITION": "intel-128",
            "allocation": {
                "requested_mode": "exclusive",
                "scheduler_oversubscribe": "NO",
                "scheduler_exclusive": None,
            },
        },
    }
    profiles = {}
    for index, profile in enumerate(COMPARISON.EXPECTED_PROFILES, start=1):
        duration = float(index * (1 if solver == "gurobi" else 2))
        energy = float(index * (10 if solver == "gurobi" else 15))
        profiles[profile] = {
            "accepted": True,
            "energy": {
                "runs": [_run(profile, solver, duration, energy)],
            },
        }
    summary = {
        "solver": solver,
        "profiles": profiles,
        "gate": {"accepted": True},
    }
    (root / "research_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    (root / "profile_matrix_summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )


class DualSolverComparisonTests(unittest.TestCase):
    def test_builds_paired_one_core_comparison_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            gurobi = base / "gurobi"
            scip = base / "scip"
            output = base / "evidence"
            gurobi.mkdir()
            scip.mkdir()
            workload_sha = "c" * 64
            _write_campaign(gurobi, "gurobi", workload_sha=workload_sha)
            _write_campaign(scip, "scip", workload_sha=workload_sha)

            report = COMPARISON.build_comparison(gurobi, scip)
            paths = COMPARISON.write_evidence(report, output)

            self.assertTrue(report["gate"]["accepted"])
            self.assertEqual(len(report["paired_comparisons"]), 3)
            self.assertEqual(
                report["paired_comparisons"][0][
                    "scip_to_gurobi_duration_ratio"
                ],
                2.0,
            )
            self.assertEqual(
                report["paired_comparisons"][0]["scip_to_gurobi_energy_ratio"],
                1.5,
            )
            self.assertEqual(
                report["paired_comparisons"][0]["scip_to_gurobi_edp_ratio"],
                3.0,
            )
            self.assertTrue(all(path.is_file() for path in paths.values()))
            self.assertNotIn("\r", paths["measurements"].read_text())
            self.assertEqual(
                len(paths["checksums"].read_text().splitlines()),
                3,
            )

    def test_rejects_different_workload_fingerprints(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            gurobi = base / "gurobi"
            scip = base / "scip"
            gurobi.mkdir()
            scip.mkdir()
            _write_campaign(gurobi, "gurobi", workload_sha="c" * 64)
            _write_campaign(scip, "scip", workload_sha="d" * 64)

            with self.assertRaisesRegex(
                COMPARISON.ComparisonError,
                "workload fingerprints differ",
            ):
                COMPARISON.build_comparison(gurobi, scip)

    def test_rejects_unaccepted_input_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            gurobi = base / "gurobi"
            scip = base / "scip"
            gurobi.mkdir()
            scip.mkdir()
            _write_campaign(gurobi, "gurobi", workload_sha="c" * 64)
            _write_campaign(scip, "scip", workload_sha="c" * 64)
            summary_path = scip / "profile_matrix_summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["gate"]["accepted"] = False
            summary_path.write_text(json.dumps(summary), encoding="utf-8")

            with self.assertRaisesRegex(
                COMPARISON.ComparisonError,
                "profile matrix is not accepted",
            ):
                COMPARISON.build_comparison(gurobi, scip)


if __name__ == "__main__":
    unittest.main()
