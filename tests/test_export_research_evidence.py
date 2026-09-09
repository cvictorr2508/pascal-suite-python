import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("export_research_evidence.py")
SPEC = importlib.util.spec_from_file_location("export_research_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, document: dict) -> None:
    path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")


def _artifact(path: Path) -> dict:
    return {"name": path.name, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _campaign(root: Path, solver: str, commit: str) -> tuple[Path, Path]:
    root.mkdir()
    manifest = {
        "configuration": {
            "path": f"/cluster/experiments/{solver}-hard.yaml",
            "size_bytes": 512,
            "sha256": "a" * 64,
        },
        "source": {
            "git_commit": commit,
            "git_branch": f"feat/{solver}",
            "tracked_worktree_clean": True,
        },
        "runtime": {
            "hostname": "node01",
            "python_executable": "/private/venv/bin/python",
            "python_version": "3.13.15",
            "platform": "Linux-test",
            "packages": {"solver": "1.0"},
        },
        "experiment": {
            "solver": solver,
            "resources": [1],
            "repetitions": 6,
        },
        "initial_solutions": [
            {
                "path": f"/private/{solver}/case.sol",
                "workload": "/datasets/case.lp.gz",
                "profile_id": "warm-start",
                "size_bytes": 42,
                "sha256": "b" * 64,
            }
        ],
        "slurm": {
            "SLURM_JOB_ID": "123",
            "SLURM_JOB_NAME": "solver_matrix",
            "SLURM_JOB_PARTITION": "intel-128",
            "SLURM_CPUS_PER_TASK": "64",
            "allocation": {
                "requested_mode": "exclusive",
                "scheduler_oversubscribe": "NO",
                "scheduler_exclusive": None,
            },
        },
    }
    profile = {
        "profile_kind": "default",
        "accepted": True,
        "energy": {
            "attempted_run_count": 6,
            "run_count": 6,
            "invalid_run_count": 0,
            "configuration_count": 1,
            "accuracy": {
                "median_absolute_error_percent": 0.2,
                "accepted": True,
            },
            "variability": {
                "maximum_group_region_0_cv_percent": 1.0,
                "preferred": True,
            },
        },
    }
    summary = {
        "solver": solver,
        "profiles": {
            "default": profile,
            "presolve-off": {**profile, "profile_kind": "presolve-off"},
            "warm-start": {**profile, "profile_kind": "warm-start"},
        },
        "gate": {"accepted": True},
    }
    manifest_path = root / "research_manifest.json"
    summary_path = root / "profile_matrix_summary.json"
    _write_json(manifest_path, manifest)
    _write_json(summary_path, summary)
    return manifest_path, summary_path


def _fixture(root: Path) -> tuple[Path, Path, Path]:
    gurobi = root / "gurobi"
    scip = root / "scip"
    comparison = root / "comparison"
    comparison.mkdir()
    g_manifest, g_summary = _campaign(gurobi, "gurobi", "a" * 40)
    s_manifest, s_summary = _campaign(scip, "scip", "b" * 40)
    measurements = comparison / "solver_measurements.csv"
    paired = comparison / "paired_one_core_comparisons.csv"
    measurements.write_text("solver,value\ngurobi,1\nscip,2\n", encoding="utf-8")
    paired.write_text("profile,ratio\ndefault,2\n", encoding="utf-8")
    report = {
        "comparison_scope": {
            "region_id": "0.2",
            "region_semantics": "solve execution",
            "paired_resources": [1],
            "profiles": ["default", "presolve-off", "warm-start"],
            "performance_claim_status": "controlled-comparison",
        },
        "gate": {
            "accepted": True,
            "exclusive_allocation_verified": True,
            "same_partition": True,
        },
        "dataset": {
            "fingerprints_match": True,
            "workloads": [
                {"name": "case.lp.gz", "size_bytes": 100, "sha256": "c" * 64}
            ],
        },
        "inputs": {
            "gurobi": {
                "research_manifest": _artifact(g_manifest),
                "profile_summary": _artifact(g_summary),
            },
            "scip": {
                "research_manifest": _artifact(s_manifest),
                "profile_summary": _artifact(s_summary),
            },
        },
        "paired_comparisons": [
            {
                "profile": profile,
                "scip_to_gurobi_duration_ratio": 2.0,
                "scip_to_gurobi_energy_ratio": 3.0,
                "scip_to_gurobi_edp_ratio": 6.0,
            }
            for profile in ("default", "presolve-off", "warm-start")
        ],
    }
    report_path = comparison / "dual_solver_comparison.json"
    _write_json(report_path, report)
    (comparison / "SHA256SUMS").write_text(
        "".join(
            f"{_sha256(path)}  {path.name}\n"
            for path in (report_path, measurements, paired)
        ),
        encoding="utf-8",
    )
    return gurobi, scip, comparison


class PortableEvidenceTests(unittest.TestCase):
    def test_exports_deterministic_path_neutral_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gurobi, scip, comparison = _fixture(root)
            manifest = MODULE.build_portable_manifest(gurobi, scip, comparison)
            output = root / "portable"
            paths = MODULE.write_portable_evidence(manifest, output)

            serialized = paths["manifest"].read_text(encoding="utf-8")
            self.assertEqual(manifest["evidence_class"], "controlled-dual-solver-research-mvp")
            self.assertNotIn(str(root), serialized)
            self.assertNotIn("/private/", serialized)
            self.assertEqual(len(manifest["artifacts"]), 7)
            expected = f"{_sha256(paths['manifest'])}  evidence_manifest.json\n"
            self.assertEqual(paths["checksums"].read_text(encoding="utf-8"), expected)

    def test_rejects_tampered_campaign_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gurobi, scip, comparison = _fixture(root)
            (gurobi / "profile_matrix_summary.json").write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(MODULE.EvidenceError, "does not match"):
                MODULE.build_portable_manifest(gurobi, scip, comparison)

    def test_rejects_exploratory_comparison(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            gurobi, scip, comparison = _fixture(root)
            report_path = comparison / "dual_solver_comparison.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["gate"]["accepted"] = False
            report["comparison_scope"]["performance_claim_status"] = "exploratory-only"
            _write_json(report_path, report)

            with self.assertRaisesRegex(MODULE.EvidenceError, "not controlled"):
                MODULE.build_portable_manifest(gurobi, scip, comparison)


if __name__ == "__main__":
    unittest.main()

