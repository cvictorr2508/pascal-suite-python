import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "summarize_solver_profile_matrix.py"
SPEC = importlib.util.spec_from_file_location("profile_matrix_summary", SCRIPT_PATH)
SUMMARY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SUMMARY)


def _energy_summary():
    return {
        "attempted_run_count": 1,
        "run_count": 1,
        "invalid_run_count": 0,
        "configuration_count": 1,
        "configuration_count_accepted": True,
        "accuracy": {
            "accepted": True,
            "median_absolute_error_percent": 1.0,
        },
        "variability": {
            "preferred": True,
            "maximum_group_region_0_cv_percent": 2.0,
        },
    }


def _write_matrix(root: Path, solver: str) -> None:
    manifest = {
        "source": {"git_commit": "a" * 40},
        "experiment": {
            "solver": solver,
            "resources": [1],
            "repetitions": 1,
            "profiles": [
                {
                    "id": "default",
                    "kind": "default",
                    "objective_sense": "minimize",
                },
                {
                    "id": "presolve-off",
                    "kind": "presolve-off",
                    "objective_sense": "minimize",
                },
                {
                    "id": "warm-start",
                    "kind": "warm-start",
                    "objective_sense": "minimize",
                },
            ],
        },
        "workloads": [{"path": "/data/instance.lp.gz"}],
    }
    (root / "research_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    for profile_id, profile_kind in (
        ("default", "default"),
        ("presolve-off", "presolve-off"),
        ("warm-start", "warm-start"),
    ):
        directory = root / solver / profile_id
        directory.mkdir(parents=True)
        (directory / "telemetry_pascal.json").write_text(
            "{}",
            encoding="utf-8",
        )
        (directory / "base_config.json").write_text(
            json.dumps({"profile": {"id": profile_id}}),
            encoding="utf-8",
        )
        effective = (
            {"TimeLimit": 300.0}
            if solver == "gurobi"
            else {"limits/time": 300.0}
        )
        if profile_kind == "presolve-off":
            effective.update(
                {"Presolve": 0}
                if solver == "gurobi"
                else {"presolve": "off"}
            )
        initial_solution = {"applied": False}
        if profile_kind == "warm-start":
            initial_solution = {
                "applied": True,
                "accepted": True,
                "format": "mst" if solver == "gurobi" else "sol.gz",
            }
        metadata = {
            "profile": {
                "id": profile_id,
                "objective_sense": "minimize",
            },
            "objective_sense": {
                "requested": "minimize",
                "source_name": "maximize",
                "effective_name": "minimize",
                "overridden": True,
            },
            "parameters": {"profile_effective": effective},
            "initial_solution": initial_solution,
            "metrics": {
                "status_name": "TIME_LIMIT" if solver == "gurobi" else None,
                "status": "timelimit" if solver == "scip" else None,
                "objective": 100.0,
                "best_bound": 10.0,
                "mip_gap": 0.9 if solver == "gurobi" else None,
                "gap": 0.9 if solver == "scip" else None,
            },
        }
        (directory / "meta_1.json").write_text(
            json.dumps(metadata),
            encoding="utf-8",
        )


class SolverProfileMatrixSummaryTests(unittest.TestCase):
    def test_hard_campaigns_have_redundant_attempts_and_three_profiles(self):
        for filename in (
            "gurobi-hard-profiles.yaml",
            "scip-hard-profiles.yaml",
        ):
            with self.subTest(filename=filename):
                configuration = (
                    PROJECT_ROOT / "experiments" / filename
                ).read_text(encoding="utf-8")
                self.assertIn("repetitions: 6", configuration)
                self.assertIn("id: default", configuration)
                self.assertIn("id: presolve-off", configuration)
                self.assertIn("id: warm-start", configuration)

    def test_rejects_metadata_without_effective_minimization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_matrix(root, "gurobi")
            metadata_path = root / "gurobi" / "default" / "meta_1.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["objective_sense"]["effective_name"] = "maximize"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            with patch.object(
                SUMMARY.ENERGY_SUMMARY,
                "summarize_document",
                return_value=_energy_summary(),
            ):
                result = SUMMARY.summarize_profile_matrix(
                    root,
                    required_runs=1,
                )

            self.assertFalse(result["profiles"]["default"]["accepted"])
            self.assertTrue(
                any(
                    "effective objective sense is not minimize" in error
                    for error in result["profiles"]["default"]["metadata_errors"]
                )
            )

    def test_rejects_metadata_with_wrong_time_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_matrix(root, "scip")
            metadata_path = root / "scip" / "default" / "meta_1.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["parameters"]["profile_effective"]["limits/time"] = 600
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            with patch.object(
                SUMMARY.ENERGY_SUMMARY,
                "summarize_document",
                return_value=_energy_summary(),
            ):
                result = SUMMARY.summarize_profile_matrix(
                    root,
                    required_runs=1,
                )

            self.assertFalse(result["profiles"]["default"]["accepted"])
            self.assertTrue(
                any(
                    "effective limits/time is not 300 seconds" in error
                    for error in result["profiles"]["default"]["metadata_errors"]
                )
            )

    def test_accepts_complete_matrix_for_each_solver(self):
        for solver in ("gurobi", "scip"):
            with self.subTest(solver=solver), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _write_matrix(root, solver)
                with patch.object(
                    SUMMARY.ENERGY_SUMMARY,
                    "summarize_document",
                    return_value=_energy_summary(),
                ):
                    result = SUMMARY.summarize_profile_matrix(
                        root,
                        required_runs=1,
                    )

                self.assertTrue(result["profile_set_accepted"])
                self.assertTrue(result["gate"]["accuracy_accepted"])
                self.assertTrue(result["gate"]["variability_preferred"])
                self.assertTrue(result["gate"]["accepted"])
                self.assertEqual(result["expected_attempt_count_per_profile"], 1)


if __name__ == "__main__":
    unittest.main()
