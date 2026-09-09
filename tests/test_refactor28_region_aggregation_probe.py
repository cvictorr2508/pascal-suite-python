from pathlib import Path
import unittest


class Refactor28RegionAggregationProbeTests(unittest.TestCase):
    def test_probe_exercises_documented_regional_aggregation(self):
        source = Path("refactor28_region_aggregation.slurm").read_text(encoding="utf-8")

        self.assertIn('-a "$level"', source)
        self.assertIn("run_case agg_rpls_sysfs 1 --rpls sysfs", source)
        self.assertIn("run_case agg_both_sysfs 1 --rple sysfs --rpls sysfs", source)
        self.assertIn("--ragt acc", source)
        self.assertIn("summarize_refactor28_region_energy.py", source)
        self.assertIn("#SBATCH --partition=intel-128", source)


if __name__ == "__main__":
    unittest.main()
