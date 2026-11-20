"""Synthetic offline tests. Fixtures are not campaign measurements."""

import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_scip_retry_composition import audit, contract, digest, main  # noqa: E402


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def metadata(index, seed, timestamp):
    return {
        "solver": "scip",
        "workload": "CFL_hard_instance_15.lp.gz",
        "profile": {"id": "default", "objective_sense": "minimize"},
        "cores": 1,
        "input_idx": index,
        "start_timestamp": timestamp,
        "objective_sense": {"effective_name": "minimize"},
        "parameters": {
            "seed_requested": seed,
            "seed_effective": seed,
            "threads_requested": 1,
            "threads_effective": 1,
            "parallelism_mode": "serial",
            "profile_requested": {"limits/time": 300},
            "profile_effective": {"limits/time": 300},
        },
        "metrics": {"objective": 10, "status": "timelimit"},
    }


def summary(keys, index, invalid=()):
    return {
        "profiles": {
            "default": {
                "energy": {
                    "runs": [
                        {
                            "run": key,
                            "configuration": {"input_index": index, "cores": 1},
                            "regions": {
                                "0.2": {"duration_s": 300, "energy_j": 15000},
                                "0": {"duration_s": 320, "energy_j": 16000},
                            },
                        }
                        for key in keys
                    ],
                    "invalid_runs": [{"run": key} for key in invalid],
                }
            }
        }
    }


class RetryAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.original, self.retry, self.composite = [
            base / label for label in ("original", "retry", "composite")
        ]
        self.paths = {}
        original_data = {f"1;2;{i}": {"energy": i} for i in range(1, 7)}
        retry_data = {"1;0;1": {"energy": 7}, "1;0;2": {"energy": 8}}
        composite_data = copy.deepcopy(original_data)
        composite_data["1;2;2"] = retry_data["1;0;1"]
        composite_data["1;2;3"] = retry_data["1;0;2"]
        for label, root, data, index in (
            ("original", self.original, original_data, 2),
            ("retry", self.retry, retry_data, 0),
            ("composite", self.composite, composite_data, 2),
        ):
            invalid = ("1;2;2", "1;2;3") if label == "original" else ()
            self.paths[label] = {
                "pascal_json": write(
                    root / "scip/default/test_batch_pascal.json", {"data": data}
                ),
                "research_manifest": write(
                    root / "research_manifest.json",
                    {"source": {"git_commit": "frozen"}},
                ),
                "profile_summary": write(
                    root / "profile_matrix_summary.json",
                    summary(
                        [key for key in data if key not in invalid],
                        index,
                        invalid,
                    ),
                ),
            }
        originals = []
        for i in range(1, 7):
            document = metadata(2, 10002, i)
            path = write(self.original / f"scip/default/meta_c1_i2_{i}.json", document)
            originals.append(path)
            if i not in (2, 3):
                write(self.composite / path.relative_to(self.original), document)
        added = []
        for timestamp in (7, 8):
            document = metadata(0, 10000, timestamp)
            source = write(
                self.retry / f"scip/default/meta_c1_i0_{timestamp}.json", document
            )
            document["input_idx"] = 2
            destination = write(
                self.composite / f"scip/default/meta_c1_i2_{timestamp}.json", document
            )
            added.append(
                {
                    "retry_source": str(source),
                    "retry_source_sha256": digest(source),
                    "composite_destination": str(destination),
                    "composite_sha256": digest(destination),
                    "remapped_input_index": {"from": 0, "to": 2},
                }
            )
        derived = {
            "composite_pascal_json": str(self.paths["composite"]["pascal_json"]),
            "research_manifest": str(self.paths["composite"]["research_manifest"]),
            "viewer_json": str(
                write(self.composite / "viewer.json", {"data": composite_data})
            ),
        }
        for name, hash_name in (
            ("composite_pascal_json", "composite_pascal_sha256"),
            ("research_manifest", "research_manifest_sha256"),
            ("viewer_json", "viewer_json_sha256"),
        ):
            derived[hash_name] = digest(Path(derived[name]))
        self.manifest = {
            "schema_version": 1,
            "kind": "telemetry-retry-replacement",
            "source_commit": "frozen",
            "original_root": str(self.original),
            "retry_root": str(self.retry),
            "output_root": str(self.composite),
            "derived_files": derived,
            "source_hashes": {
                f"{label}_{suffix}": digest(path)
                for label in ("original", "retry")
                for suffix, path in self.paths[label].items()
            },
            "configuration": {
                "solver": "scip",
                "cores": 1,
                "profile": "default",
                "original_input_index": 2,
                "retry_input_index": 0,
                "workload": "CFL_hard_instance_15.lp.gz",
            },
            "replacements": [
                {"original_run": "1;2;2", "retry_run": "1;0;1"},
                {"original_run": "1;2;3", "retry_run": "1;0;2"},
            ],
            "metadata_added": added,
            "metadata_removed": [
                {"path": str(p), "sha256": digest(p)} for p in originals[1:3]
            ],
        }
        self.manifest_path = self.composite / "composition_manifest.json"
        self.save()

    def save(self):
        write(self.manifest_path, self.manifest)

    def test_seed_drift_does_not_erase_integrity_success(self):
        report = audit(self.manifest_path)
        self.assertTrue(report["integrity_accepted"], report["failed_checks"])
        self.assertFalse(report["retry_parameter_equivalence"])
        self.assertEqual(report["same_contract_valid_count"], 4)
        self.assertEqual(
            report["parameter_differences"][0]["fields"],
            [
                "parameters.seed_effective",
                "parameters.seed_requested",
            ],
        )
        self.assertFalse(report["causal_seed_effect_estimated"])

    def test_same_seed_contract_and_status_independence(self):
        original = metadata(2, 10002, 1)
        retry = metadata(0, 10002, 7)
        retry["metrics"] = {"objective": 999, "status": "optimal"}
        self.assertEqual(contract(original), contract(retry))

    def test_full_matching_chain_is_accepted(self):
        for entry in self.manifest["metadata_added"]:
            for key, hash_key in (
                ("retry_source", "retry_source_sha256"),
                ("composite_destination", "composite_sha256"),
            ):
                path = Path(entry[key])
                document = json.loads(path.read_text())
                document["parameters"].update(
                    seed_requested=10002, seed_effective=10002
                )
                write(path, document)
                entry[hash_key] = digest(path)
        self.save()
        report = audit(self.manifest_path)
        self.assertTrue(report["integrity_accepted"])
        self.assertTrue(report["retry_parameter_equivalence"])
        self.assertEqual(report["same_contract_valid_count"], 6)

    def test_missing_seed_fails_closed(self):
        document = metadata(0, 10000, 7)
        del document["parameters"]["seed_effective"]
        with self.assertRaisesRegex(ValueError, "Missing required parameter"):
            contract(document)

    def test_source_hash_tampering_is_detected(self):
        self.manifest["source_hashes"]["original_pascal_json"] = "0" * 64
        self.save()
        self.assertFalse(audit(self.manifest_path)["integrity_accepted"])

    def test_index_remap_cannot_hide_changed_seed_in_destination(self):
        entry = self.manifest["metadata_added"][0]
        path = Path(entry["composite_destination"])
        document = json.loads(path.read_text())
        document["parameters"]["seed_effective"] = 10002
        write(path, document)
        entry["composite_sha256"] = digest(path)
        self.save()
        report = audit(self.manifest_path)
        self.assertFalse(report["integrity_accepted"])
        self.assertTrue(
            any("index_only_remap" in key for key in report["failed_checks"])
        )

    def test_analyzer_values_cannot_be_changed(self):
        path = self.paths["composite"]["pascal_json"]
        document = json.loads(path.read_text())
        document["data"]["1;2;2"]["energy"] = 999
        write(path, document)
        self.manifest["derived_files"]["composite_pascal_sha256"] = digest(path)
        self.save()
        self.assertIn(
            "complete_analyzer_copy", audit(self.manifest_path)["failed_checks"]
        )

    def test_path_escape_is_rejected(self):
        self.manifest["metadata_added"][0]["retry_source"] = str(
            self.original / "outside.json"
        )
        self.save()
        with self.assertRaisesRegex(ValueError, "escapes"):
            audit(self.manifest_path)

    def test_audit_does_not_write_evidence(self):
        base = Path(self.temporary.name)
        before = {p: digest(p) for p in base.rglob("*") if p.is_file()}
        audit(self.manifest_path)
        self.assertEqual(before, {p: digest(p) for p in base.rglob("*") if p.is_file()})

    def test_cli_returns_three_for_known_seed_mismatch(self):
        with patch.object(
            sys, "argv", ["audit", "--manifest", str(self.manifest_path)]
        ):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 3)

    def test_duplicate_or_empty_replacements_are_not_accepted(self):
        self.manifest["replacements"] = []
        self.save()
        self.assertFalse(audit(self.manifest_path)["integrity_accepted"])

    def test_missing_input_returns_two_not_silent_success(self):
        Path(self.manifest["metadata_added"][0]["retry_source"]).unlink()
        with patch.object(
            sys, "argv", ["audit", "--manifest", str(self.manifest_path)]
        ):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 2)

    def test_observation_values_do_not_enter_parameter_selection(self):
        document = metadata(0, 10002, 7)
        baseline = contract(document)
        document["metrics"] = {"objective": 0, "gap": 1e20, "duration": 999999}
        self.assertEqual(baseline, contract(document))

    def test_missing_composite_summary_row_is_detected(self):
        path = self.paths["composite"]["profile_summary"]
        document = json.loads(path.read_text())
        document["profiles"]["default"]["energy"]["runs"].pop()
        write(path, document)
        report = audit(self.manifest_path)
        self.assertIn("composite_valid_run_membership", report["failed_checks"])
        self.assertIn("affected_cell_valid_counts", report["failed_checks"])

    def test_out_of_scope_profile_change_is_detected(self):
        write(self.original / "scip/warm-start/preserved.json", {"value": 1})
        write(self.composite / "scip/warm-start/preserved.json", {"value": 2})
        self.assertIn(
            "unchanged:warm-start/preserved.json",
            audit(self.manifest_path)["failed_checks"],
        )

    def test_unknown_schema_is_not_accepted(self):
        self.manifest["schema_version"] = 2
        self.save()
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            audit(self.manifest_path)


class RecordedFindingTests(unittest.TestCase):
    def test_reported_npad_closure_preserves_boundaries_and_diagnostics(self):
        record = json.loads(
            (ROOT / "publication/audits/scip-retry-npad-result-20261011.json")
            .read_text()
        )
        result = record["result"]
        self.assertEqual(record["reported_exit_code"], 3)
        self.assertEqual(result["checks_performed"], 135)
        self.assertEqual(result["failed_checks"], [])
        self.assertTrue(result["integrity_accepted"])
        self.assertTrue(result["diagnostic_only"])
        self.assertEqual(result["same_contract_valid_count"], 4)
        for boundary in (
            "retry_parameter_equivalence",
            "causal_seed_effect_estimated",
            "publication_artifacts_modified",
            "raw_power_reintegrated",
            "scheduler_allocation_equivalence_checked",
            "stored_summary_values_independently_recomputed",
        ):
            self.assertFalse(result[boundary], boundary)
        self.assertEqual(len(result["parameter_differences"]), 2)
        for difference in result["parameter_differences"]:
            self.assertEqual(difference["original_seed"], 10002)
            self.assertEqual(difference["retry_seed"], 10000)
        for diagnostics_key, changes_key in (
            ("cell_diagnostics", "composite_vs_original_median_change_percent"),
            (
                "pipeline_region_0_diagnostics",
                "pipeline_composite_vs_original_median_change_percent",
            ),
        ):
            diagnostics = result[diagnostics_key]
            for group, count in (("original", 4), ("retry", 2), ("composite", 6)):
                self.assertEqual(diagnostics[group]["telemetry_valid_count"], count)
            for metric, change in result[changes_key].items():
                recomputed = 100 * (
                    diagnostics["composite"][metric]
                    / diagnostics["original"][metric] - 1
                )
                self.assertAlmostEqual(recomputed, change, places=10)

    def test_audit_record_does_not_claim_zero_scientific_impact(self):
        record = json.loads(
            (ROOT / "publication/audits/scip-retry-seed-20261011.json").read_text()
        )
        self.assertFalse(record["verification_boundary"]["retry_parameter_equivalence"])
        self.assertFalse(
            record["author_editorial_decision"]["scientific_zero_impact_proven"]
        )
        self.assertFalse(record["restrictions"]["new_hpc_jobs_authorized"])
        self.assertEqual(
            record["affected_configuration"]["original_seed_effective"], 10002
        )
        self.assertEqual(
            record["affected_configuration"]["retry_seed_effective"], 10000
        )


if __name__ == "__main__":
    unittest.main()
