import importlib.util
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "summarize_refactor28_nested_energy.py"
SPEC = importlib.util.spec_from_file_location("nested_energy_summary", SCRIPT_PATH)
SUMMARY = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SUMMARY)


def _run(power=10.0, global_energy=100.0):
    return {
        "start_time": 0.0,
        "stop_time": 10.0,
        "rapl-sysfs": global_energy,
        "regions": {
            "0": [[1.0, 9.0, 1, 9, 0, "runner.py"]],
            "0.1": [[1.0, 5.0, 2, 4, 0, "runner.py"]],
            "0.2": [[5.0, 9.0, 5, 8, 0, "runner.py"]],
        },
        "sensors": {
            "rapl_sample-sysfs": [
                [power, float(timestamp)] for timestamp in range(11)
            ]
        },
    }


class Refactor28NestedEnergySummaryTests(unittest.TestCase):
    def test_campaign_runs_five_repetitions_and_enforces_acceptance_gate(self):
        yaml_source = (
            PROJECT_ROOT / "refactor28_gurobi_nested_validation.yaml"
        ).read_text(encoding="utf-8")
        slurm_source = (
            PROJECT_ROOT / "refactor28_gurobi_nested_validation.slurm"
        ).read_text(encoding="utf-8")

        self.assertIn("repetitions: 5", yaml_source)
        self.assertIn("CFL_hard_instance_20.lp.gz", yaml_source)
        self.assertIn("--require-runs 5", slurm_source)
        self.assertIn("--max-median-error-percent 5", slurm_source)
        self.assertIn("--preferred-max-cv-percent 10", slurm_source)

    def test_accepts_five_stable_runs_and_reports_canonical_regions(self):
        document = {
            "data": {f"1;0;{repetition}": _run() for repetition in range(1, 6)}
        }

        result = SUMMARY.summarize_document(document)

        self.assertEqual(result["run_count"], 5)
        self.assertTrue(result["accuracy"]["accepted"])
        self.assertEqual(
            result["accuracy"]["median_absolute_error_percent"], 0.0
        )
        self.assertTrue(result["variability"]["preferred"])
        self.assertEqual(result["variability"]["region_0_cv_percent"], 0.0)
        first_run = result["runs"][0]
        self.assertEqual(first_run["regions"]["0"]["energy_j"], 80.0)
        self.assertEqual(first_run["regions"]["0.1"]["energy_j"], 40.0)
        self.assertEqual(first_run["regions"]["0.2"]["energy_j"], 40.0)
        self.assertEqual(first_run["root_coverage_percent"], 80.0)

    def test_merges_overlapping_intervals_before_integrating(self):
        samples, period = SUMMARY.normalize_power_samples(
            [[10.0, float(timestamp)] for timestamp in range(7)]
        )
        intervals = SUMMARY.merge_region_intervals(
            [[1.0, 4.0], [3.0, 6.0]]
        )

        energy, duration = SUMMARY.integrate_sampled_power(
            samples,
            period,
            intervals,
        )

        self.assertEqual(intervals, [(1.0, 6.0)])
        self.assertEqual(duration, 5.0)
        self.assertEqual(energy, 50.0)

    def test_allows_constant_endpoint_extension_for_one_sample_period(self):
        samples, period = SUMMARY.normalize_power_samples(
            [[10.0, 1.0], [10.0, 2.0]]
        )

        energy, duration = SUMMARY.integrate_sampled_power(
            samples,
            period,
            [(0.0, 3.0)],
        )

        self.assertEqual(duration, 3.0)
        self.assertEqual(energy, 30.0)

    def test_rejects_an_interval_outside_sample_coverage(self):
        samples, period = SUMMARY.normalize_power_samples(
            [[10.0, 1.0], [10.0, 2.0]]
        )

        with self.assertRaisesRegex(
            SUMMARY.EnergySummaryError,
            "do not cover",
        ):
            SUMMARY.integrate_sampled_power(
                samples,
                period,
                [(-0.1, 3.0)],
            )

    def test_accuracy_uses_whole_program_not_partial_root_region(self):
        document = {
            "data": {f"1;0;{repetition}": _run() for repetition in range(1, 6)}
        }

        result = SUMMARY.summarize_document(document)

        self.assertEqual(
            result["accuracy"]["comparison"],
            "sampled whole-program energy vs global RAPL energy",
        )
        self.assertEqual(
            result["runs"][0]["whole_program"]["sampled_energy_j"],
            100.0,
        )
        self.assertEqual(result["runs"][0]["regions"]["0"]["energy_j"], 80.0)


if __name__ == "__main__":
    unittest.main()
