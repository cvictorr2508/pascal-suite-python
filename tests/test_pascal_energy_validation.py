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
        self.assertTrue(report.legacy_region_energy_ready)
        self.assertFalse(report.sampled_energy_derivable)
        self.assertTrue(report.required_region_has_nonzero_energy)
        self.assertEqual(report.rapl_domains, ("rapl-domain-any-name",))
        self.assertEqual(
            report.legacy_region_energy_domains,
            ("rapl-domain-any-name",),
        )

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

    def test_accepts_viewer_map_without_region_energy_descriptor(self):
        document = self._regional_document(1.25)
        document["config"]["data_descriptor"]["extras"][
            "rapl-domain-any-name"
        ] = {"values": ["amount"]}

        report = validate_pascal_energy_document(document)

        self.assertTrue(report.viewer_energy_ready)
        self.assertFalse(report.legacy_region_energy_ready)
        self.assertEqual(report.legacy_region_energy_domains, ())

    def test_classifies_sampled_rapl_as_derivable_but_not_viewer_ready(self):
        document = {
            "config": {
                "data_descriptor": {
                    "values": ["start_time", "stop_time", "rapl-sysfs"],
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
                        "sensors": {"values": ["info", "time"]},
                    },
                    "keys": ["cores", "repetitions"],
                }
            },
            "data": {
                "1;1": {
                    "start_time": 0.0,
                    "stop_time": 3.0,
                    "rapl-sysfs": 150.727032,
                    "regions": {"1": [[0.003, 2.999, 27, 33, 0, "probe.c"]]},
                    "sensors": {
                        "rapl_sample-sysfs": [
                            [50.0 + (index % 3) / 10, 0.1 + index * 0.2]
                            for index in range(15)
                        ]
                    },
                }
            },
        }

        report = validate_pascal_energy_document(document)

        self.assertTrue(report.structurally_valid)
        self.assertFalse(report.viewer_energy_ready)
        self.assertFalse(report.legacy_region_energy_ready)
        self.assertTrue(report.sampled_energy_derivable)
        self.assertEqual(report.sampled_rapl_sensors, ("rapl_sample-sysfs",))
        self.assertEqual(report.runs_with_sampled_rapl, 1)
        self.assertEqual(report.runs_with_derivable_sampled_energy, 1)

    def test_rejects_sampled_rapl_that_does_not_cover_the_region(self):
        document = {
            "config": {
                "data_descriptor": {
                    "values": ["start_time", "stop_time"],
                    "extras": {
                        "regions": {"values": ["start_time", "stop_time"]},
                        "sensors": {"values": ["info", "time"]},
                    },
                }
            },
            "data": {
                "1;1": {
                    "regions": {"1": [[0.0, 10.0]]},
                    "sensors": {
                        "rapl_sample-sysfs": [[50.0, 4.0], [51.0, 4.2]]
                    },
                }
            },
        }

        report = validate_pascal_energy_document(document)

        self.assertTrue(report.structurally_valid)
        self.assertFalse(report.sampled_energy_derivable)
        self.assertEqual(report.runs_with_sampled_rapl, 1)
        self.assertEqual(report.runs_with_derivable_sampled_energy, 0)


if __name__ == "__main__":
    unittest.main()
