import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pascalpy.validation.pascal_energy import validate_pascal_energy_document


class PascalEnergyValidationTests(unittest.TestCase):
    def _regional_document(self, region_energy=0.0):
        return {
            "config": {
                "data_descriptor": {
                    "values": ["start_time", "stop_time"],
                    "extras": {
                        "regions": {
                            "values": [
                                "start_time",
                                "stop_time",
                                "start_line",
                                "stop_line",
                                "thread_id",
                                "filename",
                            ]
                        },
                        "rapl-domain-any-name": {"values": ["region_energy"]},
                    },
                    "keys": ["cores", "input", "repetitions"],
                }
            },
            "data": {
                "4;0;1": {
                    "regions": {"1": [[1.0, 2.0, 0, 0, 10, "binary"]]},
                    "rapl-domain-any-name": {"0": 10.0, "1": region_energy},
                    "start_time": 0.0,
                    "stop_time": 3.0,
                }
            },
        }

    def test_accepts_regional_energy_contract_without_hardcoded_domain_name(self):
        report = validate_pascal_energy_document(self._regional_document(1.25))

        self.assertTrue(report.structurally_valid)
        self.assertTrue(report.viewer_energy_ready)
        self.assertTrue(report.required_region_has_nonzero_energy)
        self.assertEqual(report.rapl_domains, ("rapl-domain-any-name",))

    def test_zero_energy_region_is_warning_not_structural_failure(self):
        report = validate_pascal_energy_document(self._regional_document(0.0))

        self.assertTrue(report.viewer_energy_ready)
        self.assertFalse(report.required_region_has_nonzero_energy)
        self.assertTrue(any("zero" in warning for warning in report.warnings))

    def test_rejects_global_only_rapl_schema(self):
        global_only = {
            "config": {
                "data_descriptor": {
                    "values": ["start_time", "stop_time", "rapl-sysfs"],
                    "keys": ["cores", "input", "repetitions"],
                }
            },
            "data": {
                "4;0;1": {
                    "start_time": 0.0,
                    "stop_time": 1.0,
                    "rapl-sysfs": 9.5,
                }
            },
        }

        report = validate_pascal_energy_document(global_only)

        self.assertFalse(report.structurally_valid)
        self.assertFalse(report.viewer_energy_ready)
        self.assertFalse(report.has_extras)
        self.assertEqual(report.rapl_domains, ())


if __name__ == "__main__":
    unittest.main()
