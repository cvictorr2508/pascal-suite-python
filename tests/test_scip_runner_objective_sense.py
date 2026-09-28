import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.runners import scip_runner  # noqa: E402


class _FakeScipModel:
    def __init__(self, sense="maximize"):
        self.sense = sense
        self.set_minimize_calls = 0
        self.set_maximize_calls = 0

    def getObjectiveSense(self):
        return self.sense

    def setMinimize(self):
        self.set_minimize_calls += 1
        self.sense = "minimize"

    def setMaximize(self):
        self.set_maximize_calls += 1
        self.sense = "maximize"


class _BrokenScipModel(_FakeScipModel):
    def setMinimize(self):
        self.set_minimize_calls += 1


class ScipObjectiveSenseTests(unittest.TestCase):
    def test_minimization_override_is_applied_and_recorded(self):
        model = _FakeScipModel("maximize")

        audit = scip_runner._apply_objective_sense(
            model,
            {"objective_sense": "minimize"},
        )

        self.assertEqual(model.set_minimize_calls, 1)
        self.assertEqual(audit["requested"], "minimize")
        self.assertEqual(audit["source_name"], "maximize")
        self.assertEqual(audit["effective_name"], "minimize")
        self.assertTrue(audit["overridden"])

    def test_preserve_keeps_source_objective_sense(self):
        model = _FakeScipModel("maximize")

        audit = scip_runner._apply_objective_sense(
            model,
            {"objective_sense": "preserve"},
        )

        self.assertEqual(model.set_minimize_calls, 0)
        self.assertEqual(model.set_maximize_calls, 0)
        self.assertEqual(audit["effective_name"], "maximize")
        self.assertFalse(audit["overridden"])

    def test_effective_mismatch_fails_closed(self):
        model = _BrokenScipModel("maximize")

        with self.assertRaisesRegex(
            RuntimeError,
            "Effective SCIP objective sense differs",
        ):
            scip_runner._apply_objective_sense(
                model,
                {"objective_sense": "minimize"},
            )


if __name__ == "__main__":
    unittest.main()
