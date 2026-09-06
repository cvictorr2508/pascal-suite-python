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
        self.assertIn("--require-configurations 1", slurm_source)
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
        self.assertEqual(result["configuration_count"], 1)
        self.assertEqual(result["configuration_groups"][0]["cores"], 1)
        self.assertEqual(result["configuration_groups"][0]["input_index"], 0)
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

    def test_groups_variability_by_input_and_core_configuration(self):
        data = {}
        for repetition in range(1, 6):
            data[f"1;0;{repetition}"] = _run(power=10.0, global_energy=100.0)
            data[f"4;1;{repetition}"] = _run(power=20.0, global_energy=200.0)

        result = SUMMARY.summarize_document(
            {"data": data},
            workloads=["/data/instance-5.lp.gz", "/data/instance-10.lp.gz"],
            required_configurations=2,
        )

        self.assertEqual(result["run_count"], 10)
        self.assertEqual(result["configuration_count"], 2)
        self.assertTrue(result["accuracy"]["accepted"])
        self.assertTrue(result["configuration_count_accepted"])
        self.assertTrue(result["variability"]["preferred"])
        self.assertIsNone(result["variability"]["region_0_cv_percent"])
        self.assertEqual(
            result["variability"]["maximum_group_region_0_cv_percent"],
            0.0,
        )
        self.assertEqual(
            [group["workload_name"] for group in result["configuration_groups"]],
            ["instance-5.lp.gz", "instance-10.lp.gz"],
        )

    def test_rejects_campaign_when_one_configuration_has_too_few_runs(self):
        data = {
            f"1;0;{repetition}": _run()
            for repetition in range(1, 6)
        }
        data.update(
            {
                f"2;0;{repetition}": _run()
                for repetition in range(1, 5)
            }
        )

        result = SUMMARY.summarize_document({"data": data})

        self.assertFalse(result["accuracy"]["accepted"])
        self.assertEqual(
            [group["run_count"] for group in result["configuration_groups"]],
            [5, 4],
        )

    def test_hard_campaign_covers_five_instances_and_three_core_counts(self):
        yaml_source = (
            PROJECT_ROOT / "refactor28_gurobi_hard_validation.yaml"
        ).read_text(encoding="utf-8")
        slurm_source = (
            PROJECT_ROOT / "refactor28_gurobi_hard_validation.slurm"
        ).read_text(encoding="utf-8")

        self.assertIn("resources: [1, 2, 4]", yaml_source)
        self.assertIn("repetitions: 5", yaml_source)
        for instance_id in (5, 10, 15, 20, 25):
            self.assertIn(f"CFL_hard_instance_{instance_id}.lp.gz", yaml_source)
        self.assertIn("#SBATCH --cpus-per-task=4", slurm_source)
        self.assertIn("campaign_runs=%s", slurm_source)
        self.assertIn('--base-config "$BASE_CONFIG_FILE"', slurm_source)
        self.assertIn("--require-configurations 15", slurm_source)

    def test_rejects_noncanonical_run_key(self):
        with self.assertRaisesRegex(
            SUMMARY.EnergySummaryError,
            "cores;input;repetition",
        ):
            SUMMARY.summarize_document({"data": {"1;0": _run()}})

    def test_rejects_campaign_with_missing_configuration(self):
        document = {
            "data": {f"1;0;{repetition}": _run() for repetition in range(1, 6)}
        }

        result = SUMMARY.summarize_document(
            document,
            required_configurations=2,
        )

        self.assertFalse(result["configuration_count_accepted"])
        self.assertFalse(result["accuracy"]["accepted"])

    def test_rejects_nonpositive_regional_energy(self):
        document = {
            "data": {
                f"1;0;{repetition}": _run(power=0.0, global_energy=100.0)
                for repetition in range(1, 6)
            }
        }

        with self.assertRaisesRegex(
            SUMMARY.EnergySummaryError,
            "energy must be positive",
        ):
            SUMMARY.summarize_document(document)


if __name__ == "__main__":
    unittest.main()
