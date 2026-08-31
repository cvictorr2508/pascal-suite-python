import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "summarize_pascal_loader_matrix.py"
SPEC = importlib.util.spec_from_file_location("summarize_pascal_loader_matrix", MODULE_PATH)
summary_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(summary_module)


class PascalLoaderSummaryTests(unittest.TestCase):
    def test_detects_region_one_and_duration(self):
        payload = {
            "data": {
                "1;1": {
                    "regions": {
                        "1": [[10.0, 12.25, 100, 110, 7, "diagnostic.py"]]
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = summary_module._summarize(path)

        self.assertTrue(result["exists"])
        self.assertEqual(result["run_count"], 1)
        self.assertEqual(result["runs_with_regions"], 1)
        self.assertEqual(result["runs_with_region_1"], 1)
        self.assertAlmostEqual(result["region_1_duration_s"], 2.25)

    def test_missing_file_is_reported_without_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            result = summary_module._summarize(path)

        self.assertFalse(result["exists"])
        self.assertEqual(result["run_count"], 0)
        self.assertEqual(result["runs_with_region_1"], 0)
        self.assertIsNone(result["region_1_duration_s"])


if __name__ == "__main__":
    unittest.main()
