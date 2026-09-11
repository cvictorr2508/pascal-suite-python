"""Regression tests for the historical publication-quality audit."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("publication_review", SCRIPTS / "prepare_publication_review.py")
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


class PublicationReviewTests(unittest.TestCase):
    def test_join_uses_containment_not_order(self):
        a = {"cores": 1, "input_idx": 0, "start_timestamp": 2.1}
        b = {"cores": 1, "input_idx": 0, "start_timestamp": 5.1}
        matches = review.match_metadata({"start_time": 2, "stop_time": 4}, 1, 0,
                                        [(Path("b"), b), (Path("a"), a)])
        self.assertEqual(matches, [(Path("a"), a)])

    def test_ambiguous_join_is_not_resolved_by_order(self):
        item = {"cores": 1, "input_idx": 0, "start_timestamp": 2.1}
        self.assertEqual(len(review.match_metadata({"start_time": 2, "stop_time": 4},
            1, 0, [(Path("a"), item), (Path("b"), item)])), 2)

    def test_invalid_start_time_never_matches(self):
        self.assertEqual(review.match_metadata({"start_time": 2, "stop_time": 4},
            1, 0, [(Path("a"), {"cores": 1, "input_idx": 0, "start_timestamp": True})]), [])

    def test_missing_gap_is_not_replaced_by_zero(self):
        item = {"metrics": {"status": 2, "objective": 5.0}}
        self.assertEqual(review.quality_reasons("gurobi", item), [])
        self.assertNotIn("gap", item["metrics"])

    def test_optimal_status_is_required(self):
        for status in (9, True, "2", None):
            with self.subTest(status=status):
                reasons = review.quality_reasons("gurobi", {"metrics": {"status": status, "objective": 2}})
                self.assertIn("terminal_status_not_optimal", reasons)

    def test_nonfinite_objective_rejected(self):
        for value in (float("inf"), float("nan"), True, None):
            with self.subTest(value=value):
                self.assertIn("objective_missing_or_nonfinite", review.quality_reasons(
                    "scip", {"metrics": {"status": "optimal", "objective": value}}))

    def rows(self):
        return [{"profile": "default", "workload": "case.lp", "solver": solver,
                 "included_one_core": True, "objective": 100.0, "quality_reasons": []}
                for solver in ("gurobi", "scip") for _ in range(5)]

    def test_objective_match(self):
        self.assertTrue(review.objective_pairs(self.rows())[0]["accepted"])

    def test_objective_mismatch(self):
        rows = self.rows()
        rows[-1]["objective"] = 101
        self.assertFalse(review.objective_pairs(rows)[0]["accepted"])

    def test_missing_replication(self):
        self.assertFalse(review.objective_pairs(self.rows()[:-1])[0]["accepted"])

    def test_invalid_attempt_not_used_to_repair_pair(self):
        rows = self.rows()
        rows[-1]["included_one_core"] = False
        self.assertFalse(review.objective_pairs(rows)[0]["accepted"])

    def test_redaction_preserves_measurements_and_unknowns(self):
        original = {"command": "python /home/person/app.py --token private",
                    "workloads": ["/home/person/data/case.lp"],
                    "metrics": {"gap": None, "objective": 100},
                    "data": {"rapl-sysfs": -1, "sensors": [[-5, 123]]},
                    "error": {"type": "Error", "message": "private"}}
        cleaned = review.clean(original)
        self.assertEqual(cleaned["data"], original["data"])
        self.assertEqual(cleaned["workloads"], ["case.lp"])
        self.assertIsNone(cleaned["metrics"]["gap"])
        self.assertNotIn("private", json.dumps(cleaned))
        self.assertIn("private", original["command"])

    def test_redaction_collision_fails_closed(self):
        with self.assertRaises(ValueError):
            review.clean({"/a/file": 1, "/b/file": 2})

    def test_synthetic_campaign_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            roots = {solver: folder / solver for solver in ("gurobi", "scip")}
            for solver, root in roots.items():
                manifest = {"experiment": {"solver": solver, "resources": [1], "repetitions": 5,
                    "profiles": [{"id": p, "kind": p} for p in review.PROFILES]},
                    "workloads": [{"path": "/benchmark/case.lp", "sha256": "a" * 64, "size_bytes": 10}]}
                review.write_json(root / "research_manifest.json", manifest)
                profiles = {}
                for profile in review.PROFILES:
                    directory = root / solver / profile
                    data = {}
                    for i in range(1, 6):
                        t = i * 10
                        data[f"1;0;{i}"] = {"start_time": t, "stop_time": t + 4, "rapl-sysfs": 40,
                            "sensors": {"rapl_sample-sysfs": [[10, t + j] for j in range(5)]},
                            "regions": {"0": [[t, t+4]], "0.1": [[t, t+2]], "0.2": [[t+2, t+4]]}}
                        review.write_json(directory / f"meta_{i}.json", {"solver": solver,
                            "profile": {"id": profile}, "cores": 1, "input_idx": 0,
                            "workload": "/benchmark/case.lp", "start_timestamp": t + 0.1,
                            "initial_solution": {"applied": True, "accepted": True},
                            "metrics": {"status": 2 if solver == "gurobi" else "optimal", "objective": 100}})
                    doc = {"config": {"command": "private /home/user/x"}, "data": data}
                    fresh = review.energy.summarize_document(doc, workloads=["/benchmark/case.lp"])
                    profiles[profile] = {"energy": fresh}
                    review.write_json(directory / "exp_pascal.json", doc)
                    review.write_json(directory / "summary.json", profiles[profile])
                    review.write_json(directory / "base_config.json", {"workloads_list": ["/benchmark/case.lp"]})
                review.write_json(root / "profile_matrix_summary.json", {"profiles": profiles})
            before = review.sha256(roots["gurobi"] / "research_manifest.json")
            fake = {"gate": {"accepted": True}, "measurements": [{"x": 1}], "paired_comparisons": [{"x": 1}]}
            with patch.object(review.comparison, "build_comparison", return_value=fake):
                report, archive = review.prepare(roots["gurobi"], roots["scip"], folder / "deposit", expected_workloads=1)
            self.assertTrue(report["quality_audit_accepted"])
            self.assertFalse(report["publication_ready"])
            self.assertNotIn("Data license decision", report["publication_blockers"])
            self.assertEqual(report["attempts"], 30)
            self.assertTrue(archive.is_file())
            self.assertEqual(
                (folder / "deposit" / "LICENSE").read_bytes(),
                (Path(__file__).resolve().parents[1] / "LICENSE").read_bytes(),
            )
            self.assertEqual(review.sha256(roots["gurobi"] / "research_manifest.json"), before)
            distributed = review.read_json(folder / "deposit/campaigns/gurobi/gurobi/default/exp_pascal.json")
            original = review.read_json(roots["gurobi"] / "gurobi/default/exp_pascal.json")
            self.assertEqual(distributed["data"], original["data"])
            self.assertNotIn("private", json.dumps(distributed))
            for line in (folder / "deposit/SHA256SUMS").read_text().splitlines():
                digest, name = line.split("  ", 1)
                self.assertEqual(digest, review.sha256(folder / "deposit" / name))
            with self.assertRaises(ValueError):
                review.prepare(roots["gurobi"], roots["scip"], folder / "deposit", expected_workloads=1)


if __name__ == "__main__":
    unittest.main()
