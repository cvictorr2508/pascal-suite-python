"""Offline regression tests for distinct, immutable result generations."""

import copy
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_publication_provenance import (  # noqa: E402
    load_snapshot,
    validate_snapshot,
)


class PublicationProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = copy.deepcopy(load_snapshot(ROOT))

    def test_current_generation_matches_frozen_tables(self):
        result = validate_snapshot(self.snapshot)
        self.assertEqual(result["paired_configurations"], 15)
        self.assertEqual(result["configurations"], 60)
        self.assertFalse(result["archival_chain_complete"])
        self.assertEqual(result["preferred_cv_exceedances"], ["scip/presolve-off"])

    def test_checksum_tampering_is_rejected(self):
        with patch.object(hashlib, "sha256") as digest:
            digest.return_value.hexdigest.return_value = "0" * 64
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                load_snapshot(ROOT)

    def test_historical_numbers_cannot_replace_corrected_validity(self):
        self.snapshot["validity"][0]["valid_runs"] = "88"
        with self.assertRaisesRegex(ValueError, "valid count mismatch"):
            validate_snapshot(self.snapshot)

    def test_missing_mandatory_gate_cannot_pass_vacuously(self):
        self.snapshot["provenance"]["gate"] = {}
        with self.assertRaisesRegex(ValueError, "comparison gate"):
            validate_snapshot(self.snapshot)

    def test_source_sense_and_budget_are_checked_independently(self):
        for key, value in (
            ("objective_sense", "maximize"),
            ("solver_time_limit_s", 28800),
        ):
            with self.subTest(key=key):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot["provenance"]["contract"][key] = value
                with self.assertRaises(ValueError):
                    validate_snapshot(snapshot)

    def test_missing_or_duplicate_configuration_is_rejected(self):
        for action in ("missing", "duplicate"):
            with self.subTest(action=action):
                snapshot = copy.deepcopy(self.snapshot)
                if action == "missing":
                    snapshot["measurements"].pop()
                else:
                    snapshot["measurements"].append(snapshot["measurements"][0])
                with self.assertRaises(ValueError):
                    validate_snapshot(snapshot)

    def test_each_configuration_requires_five_valid_attempts(self):
        self.snapshot["measurements"][0]["valid_run_count"] = "4"
        with self.assertRaisesRegex(ValueError, "under-replicated"):
            validate_snapshot(self.snapshot)

    def test_nonfinite_or_nonpositive_measurements_are_rejected(self):
        for value in ("NaN", "inf", "0", "-1"):
            with self.subTest(value=value):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot["measurements"][0]["median_solve_energy_j"] = value
                with self.assertRaisesRegex(ValueError, "invalid measurement"):
                    validate_snapshot(snapshot)

    def test_ratios_are_recomputed_from_paired_configuration_medians(self):
        self.snapshot["pairs"][0]["scip_to_gurobi_energy_ratio"] = "26.794993"
        with self.assertRaisesRegex(ValueError, "paired ratio mismatch"):
            validate_snapshot(self.snapshot)

    def test_aggregate_medians_are_checked_at_reported_precision(self):
        self.snapshot["aggregates"][0]["median_scip_to_gurobi_duration_ratio"] = "27.42"
        with self.assertRaisesRegex(ValueError, "profile median mismatch"):
            validate_snapshot(self.snapshot)

    def test_manuscript_table_drift_is_detected_without_editing_it(self):
        for name in self.snapshot["documents"]:
            with self.subTest(document=name):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot["documents"][name] = snapshot["documents"][name].replace(
                    "0.309447", "0.201043"
                )
                with self.assertRaisesRegex(ValueError, "validity table drift"):
                    validate_snapshot(snapshot)

    def test_physical_counts_do_not_silently_become_logical_counts(self):
        self.snapshot["provenance"]["counts"]["logical_attempts"] = 362
        with self.assertRaisesRegex(ValueError, "logical attempt total mismatch"):
            validate_snapshot(self.snapshot)

    def test_missing_retry_chain_cannot_be_marked_verified(self):
        self.snapshot["provenance"]["retry"][
            "full_physical_chain_independently_verified"
        ] = True
        with self.assertRaisesRegex(ValueError, "incorrectly certified"):
            validate_snapshot(self.snapshot)


if __name__ == "__main__":
    unittest.main()
