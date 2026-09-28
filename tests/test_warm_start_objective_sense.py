import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WarmStartObjectiveSenseTests(unittest.TestCase):
    def test_gurobi_exporter_forces_minimization_before_optimize(self):
        text = (
            PROJECT_ROOT / "scripts" / "export_gurobi_warm_start.py"
        ).read_text(encoding="utf-8")

        sense_position = text.index("model.ModelSense = gp.GRB.MINIMIZE")
        optimize_position = text.index("model.optimize()")

        self.assertLess(sense_position, optimize_position)
        self.assertIn('"requested": "minimize"', text)
        self.assertIn('"best_bound": float(model.ObjBound)', text)
        self.assertIn('"mip_gap": float(model.MIPGap)', text)

    def test_scip_exporter_forces_minimization_before_optimize(self):
        text = (
            PROJECT_ROOT / "scripts" / "export_scip_warm_start.py"
        ).read_text(encoding="utf-8")

        sense_position = text.index("model.setMinimize()")
        optimize_position = text.index("model.optimize()")

        self.assertLess(sense_position, optimize_position)
        self.assertIn('"requested": "minimize"', text)
        self.assertIn('"best_bound": _finite_float(model.getDualbound())', text)
        self.assertIn('"gap": _finite_float(model.getGap())', text)

    def test_warm_start_jobs_use_separate_corrected_directories_and_300s(self):
        gurobi = (
            PROJECT_ROOT / "jobs" / "prepare_gurobi_starts.slurm"
        ).read_text(encoding="utf-8")
        scip = (
            PROJECT_ROOT / "jobs" / "prepare_scip_starts.slurm"
        ).read_text(encoding="utf-8")

        self.assertIn("initial_solutions/gurobi-minimize-300s", gurobi)
        self.assertIn("--time-limit 300", gurobi)
        self.assertIn("initial_solutions/scip-minimize-300s", scip)
        self.assertIn("--time-limit 300", scip)


if __name__ == "__main__":
    unittest.main()
