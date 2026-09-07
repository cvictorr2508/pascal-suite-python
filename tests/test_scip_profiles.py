import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.runners.scip_runner import _apply_profile  # noqa: E402


class _Variable:
    def __init__(self, name):
        self.name = name


class _Model:
    def __init__(self):
        self.parameters = {}
        self.presolve_setting = None
        self.variables = [_Variable("x")]
        self.solution_values = {}
        self.solution_file = None

    def setPresolve(self, setting):
        self.presolve_setting = setting

    def setParam(self, name, value):
        self.parameters[name] = value

    def getParam(self, name):
        return self.parameters[name]

    def readSolFile(self, path):
        self.solution_file = path
        return object()

    def addSol(self, solution, free=True):
        return solution is not None and free

    def getVars(self):
        return self.variables

    def createPartialSol(self):
        return object()

    def setSolVal(self, solution, variable, value):
        self.solution_values[variable.name] = value


class ScipProfileTests(unittest.TestCase):
    def test_presolve_off_applies_solver_specific_setting(self):
        model = _Model()

        report = _apply_profile(
            model,
            Path("instance.lp"),
            {"id": "presolve-off", "kind": "presolve-off"},
        )

        self.assertIsNotNone(model.presolve_setting)
        self.assertEqual(report["parameters_effective"], {"presolve": "off"})
        self.assertFalse(report["initial_solution"]["requested"])

    def test_custom_parameter_is_applied_and_read_back(self):
        model = _Model()

        report = _apply_profile(
            model,
            Path("instance.lp"),
            {
                "id": "custom",
                "kind": "default",
                "parameters": {"limits/time": 30.0},
            },
        )

        self.assertEqual(model.parameters, {"limits/time": 30.0})
        self.assertEqual(
            report["parameters_effective"],
            {"limits/time": 30.0},
        )

    def test_solution_file_is_loaded_and_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            solution = Path(tmp) / "instance.sol"
            solution.write_text("solution status: unknown\n", encoding="utf-8")
            model = _Model()

            report = _apply_profile(
                model,
                Path("dataset/instance.lp.gz"),
                {
                    "id": "warm-start",
                    "kind": "warm-start",
                    "initial_solution": {
                        "files": {"instance.lp.gz": str(solution)},
                        "required": True,
                    },
                },
            )

        self.assertEqual(model.solution_file, str(solution.resolve()))
        self.assertTrue(report["initial_solution"]["applied"])
        self.assertTrue(report["initial_solution"]["accepted"])
        self.assertEqual(report["initial_solution"]["format"], "sol")

    def test_json_solution_assigns_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            solution = Path(tmp) / "instance.json"
            solution.write_text(
                json.dumps({"values": {"x": 1}}),
                encoding="utf-8",
            )
            model = _Model()

            report = _apply_profile(
                model,
                Path("instance.lp"),
                {
                    "id": "warm-start",
                    "kind": "warm-start",
                    "initial_solution": {
                        "files": {"instance.lp": str(solution)},
                        "required": True,
                    },
                },
            )

        self.assertEqual(model.solution_values, {"x": 1.0})
        self.assertEqual(report["initial_solution"]["variables_assigned"], 1)

    def test_gurobi_mst_is_rejected_for_scip(self):
        with tempfile.TemporaryDirectory() as tmp:
            solution = Path(tmp) / "instance.mst"
            solution.write_text("# MIP start\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                _apply_profile(
                    _Model(),
                    Path("instance.lp"),
                    {
                        "id": "warm-start",
                        "kind": "warm-start",
                        "initial_solution": {
                            "files": {"instance.lp": str(solution)},
                            "required": True,
                        },
                    },
                )


if __name__ == "__main__":
    unittest.main()
