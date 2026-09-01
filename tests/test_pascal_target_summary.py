import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "summarize_pascal_target_matrix.py"
SPEC = importlib.util.spec_from_file_location("pascal_target_summary", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PascalTargetSummaryTests(unittest.TestCase):
    def test_summarizes_requested_region_and_duration(self):
        payload = {
            "data": {
                "1;1": {
                    "regions": {
                        "9": [[10.0, 12.25, 1, 2, 3, "launcher.c"]]
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = MODULE.summarize(path, "9")

        self.assertEqual(result["runs_with_regions"], 1)
        self.assertEqual(result["runs_with_region"], 1)
        self.assertAlmostEqual(result["region_duration_s"], 2.25)

    def test_wrong_region_is_not_counted(self):
        payload = {"data": {"1;1": {"regions": {"9": [[1.0, 2.0]]}}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = MODULE.summarize(path, "1")

        self.assertEqual(result["runs_with_regions"], 1)
        self.assertEqual(result["runs_with_region"], 0)
        self.assertIsNone(result["region_duration_s"])


if __name__ == "__main__":
    unittest.main()
