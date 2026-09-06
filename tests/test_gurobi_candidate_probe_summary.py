import importlib.util
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "summarize_gurobi_candidate_probes.py"
SPEC = importlib.util.spec_from_file_location("gurobi_probe_summary", SCRIPT_PATH)
SUMMARY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SUMMARY)


class GurobiCandidateProbeSummaryTests(unittest.TestCase):
    def test_classifies_target_interval_inclusively(self):
        for runtime in (5.0, 30.0):
            document = {
                "metrics": {
                    "status_name": "OPTIMAL",
                    "gurobi_runtime_s": runtime,
                }
            }
            self.assertEqual(
                SUMMARY.classify_report(document, 5.0, 30.0), "target"
            )

    def test_time_limit_has_priority_over_runtime(self):
        document = {
            "metrics": {
                "status_name": "TIME_LIMIT",
                "gurobi_runtime_s": 60.0,
            }
        }
        self.assertEqual(
            SUMMARY.classify_report(document, 5.0, 30.0), "time_limit"
        )

    def test_non_optimal_result_is_not_selected_by_runtime(self):
        document = {
            "metrics": {
                "status_name": "INFEASIBLE",
                "gurobi_runtime_s": 10.0,
            }
        }
        self.assertEqual(
            SUMMARY.classify_report(document, 5.0, 30.0),
            "non_optimal",
        )

    def test_converts_linux_peak_rss_to_mib(self):
        document = {
            "workload": "/data/CFL_hard_instance_5.lp",
            "file_size_bytes": 2 * 1024 * 1024,
            "peak_rss_kib": 64 * 1024,
            "model": {"variables": 12, "constraints": 3},
            "metrics": {
                "status_name": "OPTIMAL",
                "gurobi_runtime_s": 10.0,
            },
        }
        row = SUMMARY.report_to_row(Path("probe.json"), document, 5.0, 30.0)
        self.assertEqual(row["instance"], "CFL_hard_instance_5")
        self.assertEqual(row["peak_rss_mib"], 64.0)
        self.assertEqual(row["file_size_mib"], 2.0)


if __name__ == "__main__":
    unittest.main()
