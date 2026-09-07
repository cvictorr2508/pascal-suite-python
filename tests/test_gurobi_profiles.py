import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.runners.gurobi_runner import _apply_profile  # noqa: E402


class _Parameters:
    Presolve = -1


class _Variable:
    def __init__(self):
        self.Start = None


class _Model:
    def __init__(self):
        self.Params = _Parameters()
        self.parameters = {}
        self.read_paths = []
        self.variables = {"x": _Variable()}

    def setParam(self, name, value):
        self.parameters[name] = value
        setattr(self.Params, name, value)

    def read(self, path):
        self.read_paths.append(path)

    def getVarByName(self, name):
        return self.variables.get(name)


class GurobiProfileTests(unittest.TestCase):
    def test_presolve_off_applies_and_records_effective_parameter(self):
        model = _Model()

        report = _apply_profile(
            model,
            Path("instance.lp"),
            {"id": "presolve-off", "kind": "presolve-off"},
        )

        self.assertEqual(model.parameters, {"Presolve": 0})
        self.assertEqual(report["parameters_effective"], {"Presolve": 0})
        self.assertFalse(report["initial_solution"]["requested"])

    def test_solver_solution_file_is_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            solution = Path(tmp) / "instance.mst"
            solution.write_text("# MIP start", encoding="utf-8")
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

        self.assertEqual(model.read_paths, [str(solution.resolve())])
        self.assertTrue(report["initial_solution"]["applied"])
        self.assertEqual(report["initial_solution"]["format"], "mst")

    def test_json_solution_assigns_start_attribute(self):
        with tempfile.TemporaryDirectory() as tmp:
            solution = Path(tmp) / "instance.json"
            solution.write_text(json.dumps({"values": {"x": 1}}), encoding="utf-8")
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

        self.assertEqual(model.variables["x"].Start, 1.0)
        self.assertEqual(report["initial_solution"]["variables_assigned"], 1)

    def test_missing_required_solution_fails(self):
        with self.assertRaises(FileNotFoundError):
            _apply_profile(
                _Model(),
                Path("instance.lp"),
                {
                    "id": "warm-start",
                    "kind": "warm-start",
                    "initial_solution": {"files": {}, "required": True},
                },
            )


if __name__ == "__main__":
    unittest.main()


